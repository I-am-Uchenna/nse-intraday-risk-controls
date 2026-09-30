"""Synthetic schema and timing checks; no instructor data is embedded here."""

import io
import unittest
from datetime import datetime, timedelta

from path_robust.engine import IST
from path_robust.vendor import VendorRow, iter_vendor_rows


HEADER8 = "<ticker>,<date>,<time>,<open>,<high>,<low>,<close>,<volume>"
HEADER9 = HEADER8 + ",<o/i>"
ROW = "SYNTHETIC,03/04/2021,09:15:00,100,101,99,100.5,250"


def parse(text):
    return list(iter_vendor_rows(io.StringIO(text), "SYNTHETIC"))


class VendorParserTests(unittest.TestCase):
    def test_declared_ninth_column_is_retained_without_interpretation(self):
        row = parse(HEADER9 + "\n" + ROW + ",not-assumed-open-interest\n")[0]
        self.assertEqual(row.extra, "not-assumed-open-interest")
        self.assertEqual(row.volume, 250)
        self.assertIsNone(row.raw_timestamp.tzinfo)

    def test_blank_ninth_header_and_blank_value_are_supported(self):
        row = parse(HEADER8 + ",\n" + ROW + ",\n")[0]
        self.assertEqual(row.extra, "")

    def test_explicit_eight_column_header_has_no_extra(self):
        self.assertIsNone(parse(HEADER8 + "\n" + ROW + "\n")[0].extra)

    def test_header_outer_whitespace_and_utf8_bom_are_normalized(self):
        header = "\ufeff" + " , ".join(HEADER9.split(",")) + " "
        row = parse(header + "\n" + ROW + ",0\n")[0]
        self.assertEqual(row.symbol, "SYNTHETIC")

    def test_mm_dd_is_explicit_even_when_day_first_would_also_parse(self):
        row = parse(HEADER8 + "\n" + ROW)[0]
        self.assertEqual(row.raw_timestamp, datetime(2021, 3, 4, 9, 15))
        with self.assertRaisesRegex(ValueError, "line 2"):
            parse(HEADER8 + "\n" + ROW.replace("03/04/2021", "13/02/2021"))

    def test_date_time_width_and_separator_are_not_guessed(self):
        for malformed in (ROW.replace("03/04/2021", "3/4/2021"),
                          ROW.replace("03/04/2021", "2021-03-04"),
                          ROW.replace("09:15:00", "9:15:00"),
                          ROW.replace("09:15:00", "09:15")):
            with self.subTest(malformed=malformed), self.assertRaisesRegex(ValueError, "exact MM/DD/YYYY"):
                parse(HEADER8 + "\n" + malformed)

    def test_invalid_calendar_date_and_nonminute_labels_are_rejected(self):
        for malformed in (ROW.replace("03/04/2021", "02/30/2021"),
                          ROW.replace("09:15:00", "09:15:01")):
            with self.subTest(malformed=malformed), self.assertRaises(ValueError):
                parse(HEADER8 + "\n" + malformed)

    def test_symbol_mismatch_is_not_relabelled(self):
        with self.assertRaisesRegex(ValueError, "symbol mismatch"):
            parse(HEADER8 + "\n" + ROW.replace("SYNTHETIC", "OTHER"))

    def test_unknown_and_headerless_schemas_are_rejected(self):
        for text in (ROW + ",0", "20210304,0915,100,101,99,100,250,0",
                     HEADER8.replace("<close>", "<last>") + "\n" + ROW,
                     HEADER8 + ",<unknown>\n" + ROW + ",0"):
            with self.subTest(text=text), self.assertRaisesRegex(ValueError, "headerless.*unknown schemas"):
                parse(text)

    def test_column_count_must_match_declared_header_exactly(self):
        for text in (HEADER8 + "\n" + ROW + ",0", HEADER9 + "\n" + ROW,
                     HEADER9 + "\n" + ROW + ",0,extra"):
            with self.subTest(text=text), self.assertRaisesRegex(ValueError, "exactly.*columns"):
                parse(text)

    def test_invalid_and_nonfinite_ohlc_are_rejected(self):
        for fields in ("100,99,98,100", "0,101,0,100", "100,nan,99,100",
                       "100,inf,99,100", "100,101,99,-1"):
            with self.subTest(fields=fields), self.assertRaisesRegex(ValueError, "OHLC"):
                parse(HEADER8 + "\nSYNTHETIC,03/04/2021,09:15:00," + fields + ",250")

    def test_volume_must_be_finite_nonnegative_but_zero_is_allowed(self):
        for volume in ("-1", "nan", "inf", ""):
            with self.subTest(volume=volume), self.assertRaises(ValueError):
                parse(HEADER8 + "\n" + ROW.rsplit(",", 1)[0] + "," + volume)
        row = parse(HEADER8 + "\n" + ROW.rsplit(",", 1)[0] + ",0")[0]
        self.assertEqual(row.volume, 0)

    def test_duplicate_and_out_of_order_raw_labels_are_rejected(self):
        for clock in ("09:15:00", "09:14:00"):
            with self.subTest(clock=clock), self.assertRaisesRegex(ValueError, "strictly increasing"):
                parse(HEADER8 + "\n" + ROW + "\n" + ROW.replace("09:15:00", clock))

    def test_missing_minutes_remain_a_gap(self):
        rows = parse(HEADER8 + "\n" + ROW + "\n" + ROW.replace("09:15:00", "09:19:00"))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1].raw_timestamp - rows[0].raw_timestamp, timedelta(minutes=4))

    def test_blank_data_rows_are_errors_not_silently_dropped(self):
        with self.assertRaisesRegex(ValueError, "line 3.*found 0"):
            parse(HEADER8 + "\n" + ROW + "\n\n" + ROW.replace("09:15:00", "09:16:00"))

    def test_empty_file_requires_a_header(self):
        with self.assertRaisesRegex(ValueError, "empty"):
            parse("")

    def test_malformed_quoted_csv_has_a_clear_line_error(self):
        with self.assertRaisesRegex(ValueError, "CSV syntax.*line 2"):
            parse(HEADER9 + "\n" + ROW + ',"unfinished')

    def test_stream_is_lazy_and_does_not_read_ahead_or_materialize(self):
        def lines():
            yield HEADER8 + "\n"
            yield ROW + "\n"
            raise AssertionError("The parser consumed a later row too early")

        rows = iter_vendor_rows(lines(), "SYNTHETIC")
        first = next(rows)
        self.assertEqual(first.open, 100)
        with self.assertRaisesRegex(AssertionError, "too early"):
            next(rows)


class VendorTimingTests(unittest.TestCase):
    def setUp(self):
        self.row = VendorRow("SYNTHETIC", datetime(2021, 3, 4, 9, 15), 100, 101, 99, 100, 250)

    def test_start_label_attaches_ist_as_an_explicit_assumption(self):
        bar = self.row.as_bar(label="start")
        self.assertEqual(bar.timestamp, datetime(2021, 3, 4, 9, 15, tzinfo=IST))
        self.assertIsNone(self.row.raw_timestamp.tzinfo)
        self.assertEqual((bar.open, bar.high, bar.low, bar.close), (100, 101, 99, 100))

    def test_end_label_shifts_back_one_minute_and_preserves_raw_label(self):
        self.assertEqual(self.row.as_bar("end").timestamp, datetime(2021, 3, 4, 9, 14, tzinfo=IST))
        self.assertEqual(self.row.raw_timestamp, datetime(2021, 3, 4, 9, 15))

    def test_end_label_midnight_shift_precedes_session_filtering(self):
        row = VendorRow("SYNTHETIC", datetime(2021, 3, 4), 100, 101, 99, 100, 0)
        self.assertEqual(row.as_bar("end").timestamp, datetime(2021, 3, 3, 23, 59, tzinfo=IST))

    def test_unknown_timing_convention_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "label must"):
            self.row.as_bar("auto")

    def test_vendor_row_does_not_claim_verified_timezone(self):
        with self.assertRaisesRegex(ValueError, "naive source label"):
            VendorRow("SYNTHETIC", datetime(2021, 3, 4, 9, 15, tzinfo=IST), 100, 101, 99, 100, 0)


if __name__ == "__main__":
    unittest.main()
