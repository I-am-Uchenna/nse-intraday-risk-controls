import tempfile
import unittest
from pathlib import Path

from path_robust.data import load_bars


class CsvTests(unittest.TestCase):
    def load_text(self, text):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bars.csv"
            path.write_text(text, encoding="utf-8")
            return load_bars(path, "SYNTHETIC")

    def test_csv_preserves_timezone_and_prices(self):
        bars = self.load_text("symbol,timestamp,open,high,low,close\n"
                              "SYNTHETIC,2024-01-02T10:00:00+05:30,100,101,99,100.5\n")
        self.assertEqual(bars[0].timestamp.isoformat(), "2024-01-02T10:00:00+05:30")
        self.assertEqual(bars[0].close, 100.5)

    def test_ambiguous_naive_timestamp_reports_input_line(self):
        with self.assertRaisesRegex(ValueError, "CSV line 2"):
            self.load_text("symbol,timestamp,open,high,low,close\n"
                           "SYNTHETIC,2024-01-02T10:00:00,100,101,99,100.5\n")

    def test_schema_error_is_explicit(self):
        with self.assertRaisesRegex(ValueError, "required CSV fields"):
            self.load_text("date,price\n2024-01-02,100\n")
