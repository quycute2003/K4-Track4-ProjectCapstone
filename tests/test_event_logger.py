"""Kiểm thử bộ ghi log EventLogger của Tuyên."""

import csv
import json
from pathlib import Path
import tempfile
import unittest

from src.contracts import CSV_FIELDS, DriverState, EyeObservation, FrameResult, StateDecision
from src.event_logger import EventLogger
from scripts.mock_results import mock_results


class EventLoggerTests(unittest.TestCase):
    def test_creates_csv_and_json_metadata(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = Path(temp_dir) / "test_run.csv"
            metadata = {"model": "test_model", "fps": 30.0, "threshold": 0.25}
            logger = EventLogger(str(csv_path), metadata)
            logger.close()

            json_path = csv_path.with_suffix(".json")
            self.assertTrue(csv_path.exists())
            self.assertTrue(json_path.exists())

            with open(json_path, encoding="utf-8") as jf:
                loaded_meta = json.load(jf)
            self.assertEqual(loaded_meta, metadata)

            with open(csv_path, encoding="utf-8") as cf:
                reader = csv.reader(cf)
                header = next(reader)
            self.assertEqual(tuple(header), CSV_FIELDS)

    def test_write_mock_results_and_verify_fields(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = Path(temp_dir) / "mock_run.csv"
            results = mock_results()
            with EventLogger(str(csv_path), {"name": "mock"}) as logger:
                for res in results:
                    logger.write(res)

            with open(csv_path, encoding="utf-8") as cf:
                reader = csv.DictReader(cf)
                rows = list(reader)

            self.assertEqual(len(rows), len(results))

            # Kiểm tra dòng UNKNOWN (ear is None): ear phải là chuỗi rỗng, không phải 0
            unknown_row = [r for r in rows if r["state"] == "UNKNOWN"][0]
            self.assertEqual(unknown_row["ear"], "")
            self.assertEqual(unknown_row["valid"], "0")

            # Kiểm tra dòng ALERT: alert_event = 1
            alert_rows = [r for r in rows if r["state"] == "ALERT"]
            self.assertEqual(alert_rows[0]["alert_event"], "1")
            self.assertEqual(alert_rows[1]["alert_event"], "0")

    def test_write_after_close_raises_error(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = Path(temp_dir) / "closed_run.csv"
            logger = EventLogger(str(csv_path), {})
            logger.close()
            with self.assertRaises(RuntimeError):
                logger.write(mock_results()[0])

    def test_close_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = Path(temp_dir) / "idempotent.csv"
            logger = EventLogger(str(csv_path), {})
            logger.close()
            logger.close()  # Không được văng exception


if __name__ == "__main__":
    unittest.main()
