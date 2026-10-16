"""Script đánh giá đối chiếu sự kiện cảnh báo của mô hình với nhãn chuẩn (Ground Truth).

Phụ trách: Nguyễn Hoàng Tuyên (2A202602439) - branch feature/demo-evaluation.
Tính 4 chỉ số bắt buộc theo PLAN.md và docs/evaluation.md:
1. Cảnh báo nhầm / phút (False Alerts/min)
2. Tỉ lệ phát hiện đúng (Detection Rate)
3. Thời gian trễ cảnh báo (Alert Latency: median, min, max)
4. Tỉ lệ quan sát hợp lệ (Valid Observation Ratio)

Hỗ trợ so sánh phương án cơ sở (Frame-based, alert_after=0) và hoàn chỉnh (Time-based, alert_after=1.5s).
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
import json
import math
from pathlib import Path
from statistics import median
import sys
from typing import Sequence

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


@dataclass
class GroundTruthEvent:
    start_s: float
    end_s: float
    event_type: str  # "closed" (nhắm mắt kéo dài >= 1.5s), "blink" (chớp mắt), "unknown" (mất mặt)

    @property
    def duration_s(self) -> float:
        return self.end_s - self.start_s


@dataclass
class FrameLog:
    frame_id: int
    timestamp_s: float
    ear: float | None
    valid: bool
    state: str
    closed_duration_s: float
    alert_event: bool
    processing_ms: float


@dataclass
class EvaluationMetrics:
    total_duration_s: float
    valid_duration_s: float
    valid_ratio: float
    total_gt_events: int
    detected_gt_events: int
    detection_rate: float
    false_alerts_count: int
    false_alerts_per_minute: float
    latencies: list[float]
    median_latency_s: float | None
    min_latency_s: float | None
    max_latency_s: float | None


def load_log_csv(csv_path: Path) -> list[FrameLog]:
    """Đọc file CSV log được ghi từ EventLogger."""
    if not csv_path.is_file():
        raise FileNotFoundError(f"Không tìm thấy file log: {csv_path}")

    logs: list[FrameLog] = []
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ear_val = float(row["ear"]) if row["ear"].strip() else None
            logs.append(FrameLog(
                frame_id=int(row["frame_id"]),
                timestamp_s=float(row["timestamp_s"]),
                ear=ear_val,
                valid=bool(int(row["valid"])),
                state=row["state"],
                closed_duration_s=float(row["closed_duration_s"]),
                alert_event=bool(int(row["alert_event"])),
                processing_ms=float(row["processing_ms"]),
            ))
    return logs


def load_ground_truth(gt_path: Path) -> list[GroundTruthEvent]:
    """Đọc file nhãn thủ công (Ground Truth).

    Định dạng file CSV: start_s, end_s, event_type
    Ví dụ:
    start_s,end_s,event_type
    5.2,7.5,closed
    12.0,12.3,blink
    18.0,20.0,unknown
    """
    if not gt_path.is_file():
        raise FileNotFoundError(f"Không tìm thấy file ground truth: {gt_path}")

    events: list[GroundTruthEvent] = []
    with open(gt_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            events.append(GroundTruthEvent(
                start_s=float(row["start_s"]),
                end_s=float(row["end_s"]),
                event_type=row["event_type"].strip().lower(),
            ))
    return events


def evaluate(
    logs: Sequence[FrameLog],
    gt_events: Sequence[GroundTruthEvent],
    tolerance_s: float = 0.5,
) -> EvaluationMetrics:
    """Đối chiếu log dự đoán với nhãn chuẩn để tính toán 4 chỉ số."""
    if not logs:
        raise ValueError("Danh sách log rỗng, không thể đánh giá.")

    total_duration_s = max(log.timestamp_s for log in logs) - min(log.timestamp_s for log in logs)
    if total_duration_s <= 0:
        total_duration_s = 0.001

    # 1. Tính thời lượng quan sát hợp lệ (valid frames)
    valid_frames = [log for log in logs if log.valid]
    valid_duration_s = total_duration_s * (len(valid_frames) / len(logs))
    valid_ratio = len(valid_frames) / len(logs)

    # 2. Lọc các sự kiện nhắm mắt kéo dài từ ground truth (event_type == 'closed')
    target_gt = [gt for gt in gt_events if gt.event_type == "closed"]

    # 3. Lấy tất cả các thời điểm phát sự kiện alert từ mô hình
    alert_timestamps = [log.timestamp_s for log in logs if log.alert_event]

    # 4. Ghép sự kiện 1-1 giữa GT và Alert
    matched_gt_indices: set[int] = set()
    used_alert_indices: set[int] = set()
    latencies: list[float] = []

    for gt_idx, gt in enumerate(target_gt):
        # Tìm alert đầu tiên rơi vào khoảng [start_s, end_s + tolerance_s]
        for a_idx, a_time in enumerate(alert_timestamps):
            if a_idx in used_alert_indices:
                continue
            if gt.start_s <= a_time <= gt.end_s + tolerance_s:
                matched_gt_indices.add(gt_idx)
                used_alert_indices.add(a_idx)
                latencies.append(a_time - gt.start_s)
                break

    detected_gt_events = len(matched_gt_indices)
    total_gt = len(target_gt)
    detection_rate = (detected_gt_events / total_gt) if total_gt > 0 else 1.0

    # 5. Cảnh báo nhầm (False Alerts): các alert không khớp với sự kiện GT nhắm mắt nào
    false_alerts_count = len(alert_timestamps) - len(used_alert_indices)
    # Quy đổi ra số cảnh báo nhầm / phút trên thời gian quan sát hợp lệ
    valid_minutes = max(valid_duration_s / 60.0, 0.001)
    false_alerts_per_minute = false_alerts_count / valid_minutes

    med_lat = median(latencies) if latencies else None
    min_lat = min(latencies) if latencies else None
    max_lat = max(latencies) if latencies else None

    return EvaluationMetrics(
        total_duration_s=total_duration_s,
        valid_duration_s=valid_duration_s,
        valid_ratio=valid_ratio,
        total_gt_events=total_gt,
        detected_gt_events=detected_gt_events,
        detection_rate=detection_rate,
        false_alerts_count=false_alerts_count,
        false_alerts_per_minute=false_alerts_per_minute,
        latencies=latencies,
        median_latency_s=med_lat,
        min_latency_s=min_lat,
        max_latency_s=max_lat,
    )


def print_report(name: str, metrics: EvaluationMetrics) -> None:
    """In bảng báo cáo kết quả chi tiết ra terminal."""
    lat_str = (
        f"{metrics.median_latency_s:.2f}s (min: {metrics.min_latency_s:.2f}s, max: {metrics.max_latency_s:.2f}s)"
        if metrics.median_latency_s is not None else "Không có dữ liệu"
    )
    print(f"\n=======================================================")
    print(f" BÁO CÁO ĐÁNH GIÁ: {name}")
    print(f"=======================================================")
    print(f" Tổng thời lượng video:         {metrics.total_duration_s:.1f}s ({metrics.total_duration_s / 60:.2f} phút)")
    print(f" Tỉ lệ quan sát hợp lệ:         {metrics.valid_ratio * 100:.1f}%")
    print(f" Số sự kiện nhắm mắt kéo dài:   {metrics.total_gt_events}")
    print(f" Số sự kiện phát hiện đúng:     {metrics.detected_gt_events} / {metrics.total_gt_events}")
    print(f" Tỉ lệ phát hiện (Detection):   {metrics.detection_rate * 100:.1f}%")
    print(f" Số lần cảnh báo nhầm:          {metrics.false_alerts_count}")
    print(f" Tần suất cảnh báo nhầm / phút: {metrics.false_alerts_per_minute:.2f} lần/phút")
    print(f" Thời gian trễ cảnh báo:        {lat_str}")
    print(f"=======================================================\n")


def create_template_ground_truth(output_path: Path) -> None:
    """Tạo file nhãn mẫu để người dùng gán nhãn cho video thực nghiệm."""
    rows = [
        {"start_s": "5.0", "end_s": "7.5", "event_type": "closed"},
        {"start_s": "12.0", "end_s": "12.3", "event_type": "blink"},
        {"start_s": "18.5", "end_s": "21.0", "event_type": "closed"},
        {"start_s": "25.0", "end_s": "27.0", "event_type": "unknown"},
        {"start_s": "32.0", "end_s": "34.5", "event_type": "closed"},
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["start_s", "end_s", "event_type"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"Đã tạo file nhãn mẫu tại: {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Đánh giá kết quả cảnh báo nhắm mắt của Vin Driver Watch.")
    parser.add_argument("--log", type=Path, help="Đường dẫn file CSV log chạy mô hình (hoặc phương án hoàn chỉnh)")
    parser.add_argument("--baseline-log", type=Path, help="Đường dẫn file CSV log phương án cơ sở (alert_after=0) để so sánh")
    parser.add_argument("--ground-truth", type=Path, help="Đường dẫn file CSV nhãn thủ công")
    parser.add_argument("--tolerance", type=float, default=0.5, help="Dung sai thời gian ghép sự kiện (giây, mặc định 0.5s)")
    parser.add_argument("--create-template", type=Path, help="Tạo file nhãn mẫu tại đường dẫn chỉ định")

    args = parser.parse_args()

    if args.create_template:
        create_template_ground_truth(args.create_template)
        return

    if not args.log or not args.ground_truth:
        parser.print_help()
        print("\nVí dụ chạy:")
        print("  python -m scripts.evaluate --log data/logs/run_timed.csv --ground-truth data/labels/test.csv")
        print("  python -m scripts.evaluate --baseline-log data/logs/run_base.csv --log data/logs/run_timed.csv --ground-truth data/labels/test.csv")
        return

    gt_events = load_ground_truth(args.ground_truth)

    if args.baseline_log:
        base_logs = load_log_csv(args.baseline_log)
        base_metrics = evaluate(base_logs, gt_events, tolerance_s=args.tolerance)
        print_report("Phương án cơ sở (Frame-based, alert_after=0)", base_metrics)

    logs = load_log_csv(args.log)
    metrics = evaluate(logs, gt_events, tolerance_s=args.tolerance)
    print_report("Phương án hoàn chỉnh (Time-based State Machine)", metrics)


if __name__ == "__main__":
    main()
