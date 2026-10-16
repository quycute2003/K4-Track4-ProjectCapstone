"""Kiểm thử script đánh giá evaluate.py của Tuyên."""

from pathlib import Path
import tempfile
import unittest

from scripts.evaluate import (
    EvaluationMetrics,
    FrameLog,
    GroundTruthEvent,
    create_template_ground_truth,
    evaluate,
    load_ground_truth,
    load_log_csv,
)


class EvaluateTests(unittest.TestCase):
    def test_evaluate_calculation(self):
        # Tạo chuỗi log giả lập
        # 0s - 4s: OPEN
        # 5s - 7s: Mắt đóng kéo dài -> alert tại 6.5s
        # 8s - 12s: OPEN
        # 13s - 15s: Mắt đóng kéo dài -> không alert (miss)
        # 16s - 20s: OPEN nhưng phát alert nhầm tại 17.0s
        logs = [
            FrameLog(0, 0.0, 0.3, True, "OPEN", 0.0, False, 10.0),
            FrameLog(1, 2.0, 0.3, True, "OPEN", 0.0, False, 10.0),
            FrameLog(2, 5.0, 0.1, True, "CLOSING", 0.0, False, 10.0),
            FrameLog(3, 6.5, 0.1, True, "ALERT", 1.5, True, 10.0),
            FrameLog(4, 7.0, 0.1, True, "ALERT", 2.0, False, 10.0),
            FrameLog(5, 8.0, 0.3, True, "OPEN", 0.0, False, 10.0),
            FrameLog(6, 13.0, 0.1, True, "CLOSING", 0.0, False, 10.0),
            FrameLog(7, 15.0, 0.1, True, "CLOSING", 2.0, False, 10.0),
            FrameLog(8, 16.0, 0.3, True, "OPEN", 0.0, False, 10.0),
            FrameLog(9, 17.0, 0.3, True, "OPEN", 0.0, True, 10.0),  # Alert nhầm
            FrameLog(10, 20.0, 0.3, True, "OPEN", 0.0, False, 10.0),
        ]

        gt = [
            GroundTruthEvent(start_s=5.0, end_s=7.0, event_type="closed"),
            GroundTruthEvent(start_s=13.0, end_s=15.0, event_type="closed"),
        ]

        metrics = evaluate(logs, gt, tolerance_s=0.5)

        self.assertEqual(metrics.total_gt_events, 2)
        self.assertEqual(metrics.detected_gt_events, 1)
        self.assertEqual(metrics.detection_rate, 0.5)
        self.assertEqual(metrics.false_alerts_count, 1)
        self.assertEqual(len(metrics.latencies), 1)
        self.assertAlmostEqual(metrics.latencies[0], 1.5)  # 6.5s - 5.0s = 1.5s
        self.assertAlmostEqual(metrics.median_latency_s, 1.5)

    def test_create_and_load_template_ground_truth(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            gt_file = Path(temp_dir) / "gt.csv"
            create_template_ground_truth(gt_file)
            self.assertTrue(gt_file.exists())
            events = load_ground_truth(gt_file)
            self.assertGreater(len(events), 0)
            self.assertEqual(events[0].event_type, "closed")


if __name__ == "__main__":
    unittest.main()
