"""Vin Driver Watch: webcam/video → mốc mắt → EAR → cảnh báo.

Q/Esc: thoát; R: hiệu chỉnh lại. Không ghi hình tự động.
"""

from __future__ import annotations

import argparse
from collections import Counter
from importlib.metadata import version
import json
import math
from pathlib import Path
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from src.contracts import DriverState, FrameResult
from src.alarm import AlarmSound
from src.eye_detector import EyeDetector
from src.state_machine import DriverStateMachine


ROOT = Path(__file__).resolve().parent


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--camera", type=int, default=0)
    source.add_argument("--video", type=Path)
    parser.add_argument("--model", type=Path, default=ROOT / "models/face_landmarker.task")
    parser.add_argument("--alert-after", type=float, default=1.5, help="Giây mắt đóng liên tục; 0 = phương án cơ sở")
    parser.add_argument("--calibration-samples", type=int, default=60)
    parser.add_argument("--close-ratio", type=float, default=0.65)
    parser.add_argument("--open-ratio", type=float, default=0.75)
    parser.add_argument("--max-gap", type=float, default=0.5)
    parser.add_argument("--fps", type=float, help="FPS nguồn video khi metadata sai/thiếu; không phải FPS xử lý")
    parser.add_argument("--headless", action="store_true", help="Không mở cửa sổ (kiểm tra video)")
    parser.add_argument("--mute", action="store_true", help="Tắt tiếng bíp; headless luôn tắt âm thanh")
    parser.add_argument("--max-frames", type=int, help="Dừng sau N khung hình")
    parser.add_argument("--log", type=Path, help="CSV qua EventLogger của Tuyên, khi module đã có")
    return parser


def preview(frame, result: FrameResult, machine: DriverStateMachine, cv2):
    """Hiển thị tối thiểu để Quý tự chạy; Tuyên sở hữu overlay chính thức."""
    canvas = frame.copy()
    decision = result.decision
    color = (40, 40, 240) if decision.state == DriverState.ALERT else (80, 220, 80)
    if decision.state in (DriverState.UNKNOWN, DriverState.CALIBRATING):
        color = (0, 200, 255)
    for x, y in result.observation.eye_points:
        cv2.circle(canvas, (round(x), round(y)), 2, color, -1)
    ear = result.observation.ear
    lines = [
        f"Vin Driver Watch | {decision.state.value}",
        f"EAR: {'--' if ear is None else f'{ear:.3f}'} | closed: {decision.closed_duration_s:.2f}s",
        f"Calibration: {machine.calibration_count}/{machine.calibration_samples} (eyes open)",
        f"Source: {result.timestamp_s:.2f}s | processing: {result.processing_ms:.1f}ms",
        "One person | R: recalibrate | Q/Esc: quit",
    ]
    for index, line in enumerate(lines):
        cv2.putText(canvas, line, (12, 28 + index * 26), cv2.FONT_HERSHEY_SIMPLEX,
                    0.55, (0, 0, 0), 4, cv2.LINE_AA)
        cv2.putText(canvas, line, (12, 28 + index * 26), cv2.FONT_HERSHEY_SIMPLEX,
                    0.55, color, 1, cv2.LINE_AA)
    return canvas


def run(args: argparse.Namespace) -> int:
    machine = DriverStateMachine(
        alert_after_s=args.alert_after, calibration_samples=args.calibration_samples,
        close_ratio=args.close_ratio, open_ratio=args.open_ratio, max_gap_s=args.max_gap,
    )
    if args.max_frames is not None and args.max_frames < 1:
        raise ValueError("--max-frames phải >= 1")
    if args.fps is not None and (not math.isfinite(args.fps) or args.fps <= 0):
        raise ValueError("--fps phải hữu hạn và > 0")
    if args.video is None and args.fps is not None:
        raise ValueError("--fps chỉ dùng cho video")
    if args.video is not None and not args.video.is_file():
        raise FileNotFoundError(f"Không thấy video: {args.video}")
    # Kiểm tra trước khi xin camera; --help không cần cài các thư viện thị giác.
    if not args.model.is_file():
        raise FileNotFoundError(f"Không thấy {args.model}. Chạy python -m scripts.download_model")
    import cv2
    from src import overlay, event_logger

    draw_overlay = getattr(overlay, "draw_overlay", None)
    logger_class = getattr(event_logger, "EventLogger", None)
    if args.log and not callable(logger_class):
        raise RuntimeError("EventLogger của Tuyên chưa có; bỏ --log để chạy nhận diện")
    source = str(args.video) if args.video is not None else args.camera
    capture = None
    logger = None
    detector = None
    counts: Counter = Counter()
    events = 0
    frame_id = 0
    log_part = 1
    alarm = AlarmSound(enabled=not (args.mute or args.headless))
    try:
        detector = EyeDetector(str(args.model))
        capture = cv2.VideoCapture(source)
        if not capture.isOpened():
            raise RuntimeError("Không mở được đầu vào. Kiểm tra camera/quyền truy cập hoặc video.")
        video_fps = None
        if args.video is not None:
            video_fps = args.fps or capture.get(cv2.CAP_PROP_FPS)
            if not math.isfinite(video_fps) or video_fps <= 0:
                raise ValueError("Video thiếu FPS hợp lệ. Cung cấp --fps theo FPS nguồn.")
        start = time.monotonic()
        print("Nhìn thẳng, mở mắt bình thường để hiệu chỉnh; chỉ một người trong hình.")
        if not callable(draw_overlay):
            print("Đang dùng hiển thị tối thiểu; overlay chính thức của Tuyên chưa có.")
        while args.max_frames is None or frame_id < args.max_frames:
            ok, frame = capture.read()
            if not ok:
                if args.video is None or frame_id == 0:
                    raise RuntimeError("Mất camera hoặc không đọc được khung hình đầu vào.")
                print("Đã đọc hết video (hoặc bộ giải mã dừng đọc).")
                break
            # Video CFR: thời gian của khung hình nguồn, không phải thời gian chạy inference.
            timestamp = frame_id / video_fps if video_fps is not None else time.monotonic() - start
            before = time.perf_counter()
            observation = detector.detect(frame)
            decision = machine.update(observation, timestamp)
            result = FrameResult(frame_id, timestamp, observation, decision,
                                 (time.perf_counter() - before) * 1000)
            counts[decision.state.value] += 1
            if decision.alert_event:
                events += 1
                alarm.play()
                print(json.dumps({"event": "eyes_closed", "timestamp_s": timestamp,
                                  "closed_duration_s": decision.closed_duration_s}))
            if args.log and decision.close_threshold is not None:
                if logger is None:
                    log_path = args.log if log_part == 1 else args.log.with_name(
                        f"{args.log.stem}.part{log_part}{args.log.suffix}")
                    log_path.parent.mkdir(parents=True, exist_ok=True)
                    if log_path.exists() or log_path.with_suffix(".json").exists():
                        raise FileExistsError(f"Log đã tồn tại: {log_path}; hãy chọn tên mới")
                    metadata = {
                        "source": str(source), "source_fps": video_fps,
                        "model_path": str(args.model),
                        "mediapipe_version": version("mediapipe"),
                        "opencv_version": cv2.__version__,
                        "config": {key: getattr(args, key) for key in (
                            "alert_after", "calibration_samples", "close_ratio", "open_ratio", "max_gap")},
                        "reference_ear": machine.reference_ear,
                        "close_threshold": decision.close_threshold,
                        "open_threshold": decision.open_threshold,
                        "log_starts_after_calibration": True,
                    }
                    logger = logger_class(str(log_path), metadata)
                logger.write(result)
            if not args.headless:
                display = draw_overlay(frame, result) if callable(draw_overlay) else preview(frame, result, machine, cv2)
                cv2.imshow("Vin Driver Watch", display)
                delay = max(1, round(1000 / video_fps - result.processing_ms)) if video_fps else 1
                key = cv2.waitKey(delay) & 0xFF
                if key in (ord("q"), 27) or cv2.getWindowProperty("Vin Driver Watch", cv2.WND_PROP_VISIBLE) < 1:
                    frame_id += 1
                    break
                if key == ord("r"):
                    machine.reset()
                    if logger is not None:
                        logger.close()
                        logger = None
                        log_part += 1
            frame_id += 1
        print(json.dumps({"frames": frame_id, "alert_events": events,
                          "states": dict(counts)}, ensure_ascii=False))
        return 0
    finally:
        alarm.close()
        # Đảm bảo lỗi một tài nguyên không ngăn đóng các tài nguyên còn lại.
        try:
            if logger is not None:
                logger.close()
        finally:
            try:
                if capture is not None:
                    capture.release()
            finally:
                try:
                    if detector is not None:
                        detector.close()
                finally:
                    if not args.headless:
                        cv2.destroyAllWindows()


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return run(args)
    except KeyboardInterrupt:
        print("Đã dừng.")
        return 130
    except (ValueError, OSError, RuntimeError, ImportError) as exc:
        print(f"Lỗi: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
