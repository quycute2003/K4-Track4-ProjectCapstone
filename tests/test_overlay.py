"""Kiểm thử giao diện vẽ overlay của Tuyên."""

import unittest
import numpy as np

from src.contracts import DriverState, EyeObservation, FrameResult, StateDecision
from src.overlay import draw_overlay
from scripts.mock_results import mock_results


class OverlayTests(unittest.TestCase):
    def test_draw_overlay_returns_copy_and_preserves_original(self):
        original = np.zeros((480, 640, 3), dtype=np.uint8)
        frame_copy = original.copy()
        result = FrameResult(
            frame_id=0,
            timestamp_s=1.0,
            observation=EyeObservation(valid=True, ear_left=0.3, ear_right=0.3, ear=0.3,
                                       eye_points=((100.0, 100.0), (120.0, 100.0))),
            decision=StateDecision(state=DriverState.OPEN, close_threshold=0.2, open_threshold=0.25),
            processing_ms=12.5,
        )
        output = draw_overlay(original, result)
        self.assertIsNot(output, original)
        self.assertEqual(output.shape, original.shape)
        np.testing.assert_array_equal(original, frame_copy)

    def test_draw_overlay_all_mock_states(self):
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        for result in mock_results():
            with self.subTest(state=result.decision.state):
                output = draw_overlay(frame, result)
                self.assertIsInstance(output, np.ndarray)
                self.assertEqual(output.shape, frame.shape)

    def test_draw_overlay_alert_border_rendered(self):
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        result = FrameResult(
            frame_id=10,
            timestamp_s=2.5,
            observation=EyeObservation(valid=True, ear=0.1, ear_left=0.1, ear_right=0.1),
            decision=StateDecision(state=DriverState.ALERT, closed_duration_s=1.5, alert_event=True),
            processing_ms=8.0,
        )
        output = draw_overlay(frame, result)
        # Viền đỏ phải được vẽ ở góc trên cùng
        self.assertTrue(np.any(output[0:5, 0:5] > 0))

    def test_draw_overlay_handles_none_or_empty_frame(self):
        result = mock_results()[0]
        self.assertIsNone(draw_overlay(None, result))
        empty = np.array([], dtype=np.uint8)
        self.assertEqual(draw_overlay(empty, result).size, 0)


if __name__ == "__main__":
    unittest.main()
