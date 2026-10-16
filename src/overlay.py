"""Giao diện hiển thị trực quan (HUD) trên khung hình OpenCV.

Phụ trách: Nguyễn Hoàng Tuyên (2A202602439) - branch feature/demo-evaluation.
Hiển thị trạng thái, mốc mắt, chỉ số EAR, ngưỡng và thời lượng mắt nhắm.
Không tự suy diễn lại logic trạng thái; nhận dữ liệu trực tiếp từ FrameResult.
"""

from __future__ import annotations

import math
from typing import Sequence

import cv2
import numpy as np

from src.contracts import DriverState, FrameResult, Point


# Màu sắc BGR theo trạng thái
STATE_COLORS: dict[DriverState, tuple[int, int, int]] = {
    DriverState.OPEN: (80, 220, 80),          # Xanh lá an toàn
    DriverState.CLOSING: (0, 165, 255),       # Cam cảnh giác
    DriverState.ALERT: (40, 40, 240),         # Đỏ báo động
    DriverState.CALIBRATING: (0, 215, 255),   # Vàng hiệu chuẩn
    DriverState.UNKNOWN: (160, 160, 160),     # Xám mất dấu/thiếu dữ liệu
}

# Tiêu đề trạng thái hiển thị
STATE_LABELS: dict[DriverState, str] = {
    DriverState.OPEN: "MẮT MỞ (BÌNH THƯỜNG)",
    DriverState.CLOSING: "MẮT ĐANG NHẮM (THEO DÕI)",
    DriverState.ALERT: "CẢNH BÁO: NHẮM MẮT KÉO DÀI!",
    DriverState.CALIBRATING: "ĐANG HIỆU CHUẨN...",
    DriverState.UNKNOWN: "KHÔNG XÁC ĐỊNH (MẤT DẤU)",
}


def _draw_text_with_shadow(
    img: np.ndarray,
    text: str,
    pos: tuple[int, int],
    font_scale: float = 0.52,
    color: tuple[int, int, int] = (255, 255, 255),
    thickness: int = 1,
    shadow_color: tuple[int, int, int] = (0, 0, 0),
) -> None:
    """Vẽ chữ có viền đen bóng để luôn đọc rõ trên mọi nền ánh sáng."""
    x, y = pos
    cv2.putText(img, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, font_scale, shadow_color, thickness + 2, cv2.LINE_AA)
    cv2.putText(img, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, font_scale, color, thickness, cv2.LINE_AA)


def _draw_eye_contours(canvas: np.ndarray, points: Sequence[Point], color: tuple[int, int, int]) -> None:
    """Vẽ đường viền 6 điểm mốc cho mỗi mắt nếu có đủ dữ liệu."""
    if len(points) == 12:
        pts_left = np.array([(round(x), round(y)) for x, y in points[:6]], dtype=np.int32)
        pts_right = np.array([(round(x), round(y)) for x, y in points[6:]], dtype=np.int32)
        cv2.polylines(canvas, [pts_left], isClosed=True, color=color, thickness=1, lineType=cv2.LINE_AA)
        cv2.polylines(canvas, [pts_right], isClosed=True, color=color, thickness=1, lineType=cv2.LINE_AA)
    for x, y in points:
        cv2.circle(canvas, (round(x), round(y)), 2, color, -1, lineType=cv2.LINE_AA)


def draw_overlay(frame: np.ndarray, result: FrameResult) -> np.ndarray:
    """Vẽ mốc mắt, EAR, ngưỡng, trạng thái và thời lượng lên khung hình.

    Trả ảnh BGR mới, không sửa frame gốc.
    """
    if frame is None or frame.size == 0:
        return frame

    canvas = frame.copy()
    h, w = canvas.shape[:2]

    decision = result.decision
    obs = result.observation
    state = decision.state
    state_color = STATE_COLORS.get(state, (200, 200, 200))
    state_label = STATE_LABELS.get(state, state.value)

    # 1. Vẽ mốc mắt
    if obs.valid and obs.eye_points:
        _draw_eye_contours(canvas, obs.eye_points, state_color)

    # 2. Hiệu ứng viền cảnh báo khi ALERT
    if state == DriverState.ALERT:
        # Viền đỏ dày bao quanh khung hình
        cv2.rectangle(canvas, (0, 0), (w - 1, h - 1), (40, 40, 240), 6)
        # Banner cảnh báo trên cùng
        banner_h = 42
        sub_img = canvas[0:banner_h, 0:w]
        red_rect = np.full_img = np.full_like(sub_img, (30, 30, 200))
        cv2.addWeighted(red_rect, 0.75, sub_img, 0.25, 0, sub_img)
        _draw_text_with_shadow(
            canvas,
            "NGUY HIỂM: PHÁT HIỆN TÀI XẾ NHẮM MẮT KÉO DÀI!",
            (max(20, w // 2 - 240), 28),
            font_scale=0.7,
            color=(255, 255, 255),
            thickness=2,
        )

    # 3. HUD thông số ở góc trên bên trái với nền bán trong suốt
    hud_x, hud_y = 12, 14 if state != DriverState.ALERT else 50
    hud_w = min(420, w - 24)
    hud_h = 165

    # Làm mờ nền bảng HUD
    if hud_y + hud_h < h and hud_x + hud_w < w:
        sub_face = canvas[hud_y:hud_y + hud_h, hud_x:hud_x + hud_w]
        dark_bg = np.zeros_like(sub_face)
        cv2.addWeighted(dark_bg, 0.65, sub_face, 0.35, 0, sub_face)
        cv2.rectangle(canvas, (hud_x, hud_y), (hud_x + hud_w, hud_y + hud_h), state_color, 1)

    # 4. Các dòng thông tin trong bảng HUD
    ear_str = f"{obs.ear:.3f}" if (obs.valid and obs.ear is not None and math.isfinite(obs.ear)) else "--"
    ear_l_str = f"{obs.ear_left:.3f}" if (obs.valid and obs.ear_left is not None and math.isfinite(obs.ear_left)) else "--"
    ear_r_str = f"{obs.ear_right:.3f}" if (obs.valid and obs.ear_right is not None and math.isfinite(obs.ear_right)) else "--"

    close_th_str = f"{decision.close_threshold:.3f}" if decision.close_threshold is not None else "--"
    open_th_str = f"{decision.open_threshold:.3f}" if decision.open_threshold is not None else "--"

    lines: list[tuple[str, tuple[int, int, int], float, int]] = [
        (f"Vin Driver Watch | {state_label}", state_color, 0.52, 2),
        (f"EAR: {ear_str} (T: {ear_l_str} | P: {ear_r_str})", (240, 240, 240), 0.46, 1),
        (f"Ngưỡng: Đóng < {close_th_str} | Mở > {open_th_str}", (210, 210, 210), 0.44, 1),
        (f"Mắt đóng: {decision.closed_duration_s:.2f}s", (0, 140, 255) if decision.closed_duration_s > 0 else (180, 180, 180), 0.46, 1),
        (f"Nguồn: {result.timestamp_s:.2f}s | Xử lý: {result.processing_ms:.1f}ms", (180, 180, 180), 0.42, 1),
        ("R: Hiệu chuẩn lại | Q/Esc: Thoát", (160, 220, 255), 0.40, 1),
    ]

    line_y = hud_y + 24
    for text, col, scale, thick in lines:
        if line_y < h:
            _draw_text_with_shadow(canvas, text, (hud_x + 10, line_y), font_scale=scale, color=col, thickness=thick)
        line_y += 24

    # 5. Thanh tiến trình thời lượng nhắm mắt (nếu đang đóng mắt)
    if decision.closed_duration_s > 0 and hud_x + hud_w < w:
        bar_x = hud_x + 10
        bar_y = hud_y + hud_h - 14
        bar_w = hud_w - 20
        bar_h = 6
        cv2.rectangle(canvas, (bar_x, bar_y), (bar_x + bar_w, bar_y + bar_h), (80, 80, 80), -1)
        # Giả định ngưỡng cảnh báo chuẩn là 1.5s
        progress = min(1.0, decision.closed_duration_s / 1.5)
        fill_w = int(bar_w * progress)
        fill_col = (40, 40, 240) if progress >= 1.0 else (0, 165, 255)
        if fill_w > 0:
            cv2.rectangle(canvas, (bar_x, bar_y), (bar_x + fill_w, bar_y + bar_h), fill_col, -1)

    return canvas
