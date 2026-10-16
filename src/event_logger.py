"""Bộ ghi nhật ký CSV và cấu hình của mỗi lượt chạy.

Phụ trách: Nguyễn Hoàng Tuyên (2A202602439) - branch feature/demo-evaluation.
Ghi cấu hình metadata ra file .json cùng tên và log từng khung hình theo chuẩn CSV_FIELDS.
Dữ liệu thiếu để ô trống, không thay bằng EAR=0 để tránh sai lệch thống kê.
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any

from src.contracts import CSV_FIELDS, FrameResult


class EventLogger:
    """Ghi dữ liệu từng khung hình và metadata cấu hình để phục vụ đánh giá."""

    def __init__(self, csv_path: str, metadata: dict[str, Any]) -> None:
        self.csv_path = Path(csv_path)
        self.json_path = self.csv_path.with_suffix(".json")
        self.metadata = metadata

        # Tạo thư mục cha nếu chưa có
        self.csv_path.parent.mkdir(parents=True, exist_ok=True)

        # 1. Ghi metadata ra file JSON cùng tên
        with open(self.json_path, "w", encoding="utf-8") as json_file:
            json.dump(metadata, json_file, indent=2, ensure_ascii=False)

        # 2. Mở file CSV và ghi header
        self._file = open(self.csv_path, "w", newline="", encoding="utf-8")
        self._writer = csv.writer(self._file)
        self._writer.writerow(CSV_FIELDS)
        self._file.flush()
        self._closed = False

    def write(self, result: FrameResult) -> None:
        """Ghi một dòng kết quả của khung hình theo đúng thứ tự CSV_FIELDS."""
        if self._closed or self._file.closed:
            raise RuntimeError("EventLogger đã đóng, không thể ghi thêm.")

        obs = result.observation
        dec = result.decision

        def format_float(val: float | None, precision: int = 4) -> str:
            if val is None or not math.isfinite(val):
                return ""
            return f"{val:.{precision}f}"

        ear_left_str = format_float(obs.ear_left) if obs.valid else ""
        ear_right_str = format_float(obs.ear_right) if obs.valid else ""
        ear_str = format_float(obs.ear) if obs.valid else ""

        row = [
            result.frame_id,
            f"{result.timestamp_s:.4f}",
            ear_left_str,
            ear_right_str,
            ear_str,
            1 if obs.valid else 0,
            dec.state.value,
            f"{dec.closed_duration_s:.4f}",
            1 if dec.alert_event else 0,
            f"{result.processing_ms:.2f}",
        ]
        self._writer.writerow(row)
        self._file.flush()

    def close(self) -> None:
        """Đóng file CSV an toàn và đảm bảo tính idempotent."""
        if not self._closed:
            self._closed = True
            if hasattr(self, "_file") and not self._file.closed:
                self._file.flush()
                self._file.close()

    def __enter__(self) -> EventLogger:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()
