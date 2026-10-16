"""Kiểm tra vòng tích hợp với camera/model giả, không xin quyền webcam."""

from contextlib import redirect_stdout
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import app
from src.contracts import EyeObservation


class AppTests(unittest.TestCase):
    def setup_run(self, temporary, video=True):
        model = Path(temporary) / "model.task"
        model.touch()
        source = Path(temporary) / "sample.avi"
        source.touch()
        arguments = ["--model", str(model), "--headless", "--calibration-samples", "1"]
        if video:
            arguments += ["--video", str(source)]
        args = app.build_parser().parse_args(arguments)
        cv2 = MagicMock()
        cv2.__version__ = "test"
        capture = cv2.VideoCapture.return_value
        capture.isOpened.return_value = True
        capture.get.return_value = 25.0
        capture.read.side_effect = [(True, object()), (True, object()), (False, None)]
        detector = MagicMock()
        detector.detect.return_value = EyeObservation()
        return args, cv2, capture, detector

    def test_video_uses_source_time_and_closes_resources_at_eof(self):
        with tempfile.TemporaryDirectory() as temporary:
            args, cv2, capture, detector = self.setup_run(temporary)
            output = io.StringIO()
            with patch.dict(sys.modules, {"cv2": cv2}), patch.object(app, "EyeDetector", return_value=detector), redirect_stdout(output):
                self.assertEqual(app.run(args), 0)
            self.assertIn('"frames": 2', output.getvalue())
            self.assertIn('"UNKNOWN": 2', output.getvalue())
            capture.release.assert_called_once()
            detector.close.assert_called_once()
            cv2.imshow.assert_not_called()

    def test_video_timing_independent_of_inference_wall_time(self):
        with tempfile.TemporaryDirectory() as temporary:
            args, cv2, capture, detector = self.setup_run(temporary)
            observation = EyeObservation(True, 0.3, 0.3, 0.3)
            detector.detect.return_value = observation
            real_machine = app.DriverStateMachine
            timestamps = []

            def create_machine(**kwargs):
                machine = real_machine(**kwargs)
                original_update = machine.update
                def update(obs, timestamp):
                    timestamps.append(timestamp)
                    return original_update(obs, timestamp)
                machine.update = update
                return machine

            with patch.dict(sys.modules, {"cv2": cv2}), patch.object(app, "EyeDetector", return_value=detector), patch.object(app, "DriverStateMachine", side_effect=create_machine), redirect_stdout(io.StringIO()):
                app.run(args)
            self.assertEqual(timestamps, [0, 1 / 25])

    def test_detector_failure_still_closes_camera_and_model(self):
        with tempfile.TemporaryDirectory() as temporary:
            args, cv2, capture, detector = self.setup_run(temporary)
            detector.detect.side_effect = RuntimeError("inference failed")
            with patch.dict(sys.modules, {"cv2": cv2}), patch.object(app, "EyeDetector", return_value=detector), redirect_stdout(io.StringIO()), self.assertRaises(RuntimeError):
                app.run(args)
            capture.release.assert_called_once()
            detector.close.assert_called_once()

    def test_camera_read_failure_is_not_reported_as_successful_eof(self):
        with tempfile.TemporaryDirectory() as temporary:
            args, cv2, capture, detector = self.setup_run(temporary, video=False)
            from itertools import count
            counter = count(0, 0.04)
            with patch.dict(sys.modules, {"cv2": cv2}), patch.object(app, "EyeDetector", return_value=detector), patch("app.time.monotonic", side_effect=counter), redirect_stdout(io.StringIO()), self.assertRaises(RuntimeError):
                app.run(args)
            capture.release.assert_called_once()

    def test_invalid_video_fps_requires_explicit_override(self):
        with tempfile.TemporaryDirectory() as temporary:
            args, cv2, capture, detector = self.setup_run(temporary)
            capture.get.return_value = float("nan")
            with patch.dict(sys.modules, {"cv2": cv2}), patch.object(app, "EyeDetector", return_value=detector), self.assertRaises(ValueError):
                app.run(args)
            capture.release.assert_called_once()

    def test_logger_receives_result_and_calibrated_metadata(self):
        from src import event_logger
        with tempfile.TemporaryDirectory() as temporary:
            args, cv2, capture, detector = self.setup_run(temporary)
            args.log = Path(temporary) / "run.csv"
            detector.detect.return_value = EyeObservation(True, 0.3, 0.3, 0.3)
            logger_class = MagicMock()
            with patch.dict(sys.modules, {"cv2": cv2}), patch.object(app, "EyeDetector", return_value=detector), patch.object(event_logger, "EventLogger", logger_class, create=True), patch.object(app, "version", return_value="test"), redirect_stdout(io.StringIO()):
                app.run(args)
            metadata = logger_class.call_args.args[1]
            self.assertAlmostEqual(metadata["close_threshold"], 0.195)
            self.assertEqual(logger_class.return_value.write.call_count, 2)
            logger_class.return_value.close.assert_called_once()

    def test_long_closure_sends_one_sound_event_not_one_per_frame(self):
        with tempfile.TemporaryDirectory() as temporary:
            args, cv2, capture, detector = self.setup_run(temporary)
            args.alert_after = 0
            capture.read.side_effect = [(True, object()) for _ in range(4)] + [(False, None)]
            detector.detect.side_effect = [EyeObservation(True, 0.3, 0.3, 0.3)] + [
                EyeObservation(True, 0.1, 0.1, 0.1) for _ in range(3)]
            with patch.dict(sys.modules, {"cv2": cv2}), patch.object(app, "EyeDetector", return_value=detector), patch.object(app, "AlarmSound") as alarm, redirect_stdout(io.StringIO()):
                app.run(args)
            alarm.assert_called_once_with(enabled=False)  # headless luôn tắt loa
            alarm.return_value.play.assert_called_once()
            alarm.return_value.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
