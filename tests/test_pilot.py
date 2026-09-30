"""Synthetic checks for pilot calendar, aggregate denominators and provenance."""

from datetime import date, datetime
import hashlib
import importlib.util
from pathlib import Path
import sqlite3
import tempfile
from types import SimpleNamespace
import unittest

from path_robust.engine import Path as PricePath, Policy

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/run_pilot.py"
SPEC = importlib.util.spec_from_file_location("pilot_runner", SCRIPT)
pilot = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pilot)


def record(day, values, status="EVALUABLE", episodes=1, ambiguous=0):
    return {"date": day, "role": "evaluation", "status": status,
            "candidate_counts": {"SIGNAL": episodes}, "planned_episodes": episodes,
            "ambiguous_episodes": ambiguous, "unresolved_episodes": 0,
            "episode_entries": [(day + "_trade", day + "T09:46", day + "T10:01")] if episodes else [],
            "accounts": [{"policy": policy.value, "path": path.value,
                          "net_daily_return_bp": values[i] if values else None,
                          "minimum_available_cash": 50_000}
                         for path in PricePath for i, policy in enumerate(Policy)]}


class PilotAggregationTests(unittest.TestCase):
    def test_day_record_deduplicates_an_episode_across_six_executions(self):
        result = SimpleNamespace(
            session_date=date(2021, 2, 1), status="EVALUABLE", issues=(), scenarios=(),
            candidates=(SimpleNamespace(status="SIGNAL"),),
            episodes=(SimpleNamespace(episode_id="one", entry_at=datetime(2021, 2, 1, 9, 46),
                                      expiry_at=datetime(2021, 2, 1, 10, 1)),),
            executions=tuple(SimpleNamespace(episode_id="one", status="RESOLVED", exit_order_ambiguous=True)
                             for _ in range(6)))
        summarized = pilot.day_record(result, "evaluation")
        self.assertEqual(summarized["planned_episodes"], 1)
        self.assertEqual(summarized["ambiguous_episodes"], 1)

    def test_calendar_is_sixty_one_declared_sessions_with_outage_retained(self):
        sessions = pilot.calendar_sessions({"start_date": "2021-01-01", "end_date": "2021-03-31",
                                           "holidays": ["2021-01-26", "2021-03-11", "2021-03-29"]})
        self.assertEqual(len(sessions), 61)
        self.assertEqual(sessions[19], date(2021, 1, 29))
        self.assertIn(date(2021, 2, 24), sessions)
        self.assertNotIn(date(2021, 1, 26), sessions)

    def test_eligible_zero_days_enter_denominator_and_incomplete_days_do_not(self):
        records = [record("2021-02-01", [2, 4, 6], ambiguous=1),
                   record("2021-02-02", [0, 0, 0], episodes=0),
                   record("2021-02-03", None, status="UNRESOLVED_POSITIONS")]
        diagnostics, means, contrasts = pilot.aggregate_run(records)
        self.assertEqual(diagnostics["common_evaluable_days"], 2)
        self.assertEqual(diagnostics["evaluable_zero_trade_days"], 1)
        self.assertEqual(diagnostics["ambiguous_unique_episodes_evaluable_days"], 1)
        self.assertEqual(means[0]["mean_net_daily_return_bp"], 1)
        self.assertEqual(contrasts[0]["mean_paired_difference_bp"], 2)

    def test_empty_evaluable_cohort_is_none_not_zero(self):
        _, means, contrasts = pilot.aggregate_run([record("2021-02-01", None, "WARMUP")])
        self.assertTrue(all(row["mean_net_daily_return_bp"] is None for row in means))
        self.assertTrue(all(row["mean_paired_difference_bp"] is None for row in contrasts))

    def test_sensitivity_uses_intersection_and_exposes_changed_entry_times(self):
        baseline = [record("2021-02-01", [1, 2, 3]), record("2021-02-02", [100, 100, 100])]
        variant = [record("2021-02-01", [2, 3, 4]), record("2021-02-03", [-100, -100, -100])]
        compared = pilot.compare_settings(baseline, variant)
        self.assertTrue(all(r["intersection_days"] == 1 for r in compared))
        self.assertTrue(all(r["mean_variant_minus_reference_bp"] == 1 for r in compared))
        self.assertTrue(all(r["identical_entries_on_intersection"] for r in compared))
        variant[0]["episode_entries"][0] = ("2021-02-01_trade", "2021-02-01T09:47", "2021-02-01T10:02")
        self.assertFalse(pilot.compare_settings(baseline, variant)[0]["identical_entries_on_intersection"])

    def test_evaluable_day_cannot_contain_missing_scenario_value(self):
        bad = record("2021-02-01", [1, 2, 3])
        bad["accounts"][0]["net_daily_return_bp"] = None
        with self.assertRaisesRegex(ValueError, "missing scenario"):
            pilot.aggregate_run([bad])

    def test_protocol_hash_mismatch_fails_before_replay(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "config.json"
            config.write_text("{}", encoding="utf-8")
            connection = sqlite3.connect(":memory:")
            try:
                with self.assertRaisesRegex(ValueError, "protocol hash"):
                    pilot.verify_inputs(connection, {"protocol_sha256": "wrong"}, config)
            finally:
                connection.close()

    def test_database_price_change_invalidates_source_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "config.json"
            config.write_text("{}", encoding="utf-8")
            connection = sqlite3.connect(":memory:")
            connection.execute("CREATE TABLE bars(symbol,stamp,o,h,l,c,volume,source_id)")
            row = ("SYNTHETIC", "2021-01-01T09:15:00", 100.0, 101.0, 99.0, 100.0, 5.0, 1)
            connection.execute("INSERT INTO bars VALUES(?,?,?,?,?,?,?,?)", row)
            audit = {"protocol_sha256": pilot.hash_file(config), "input_files": [{
                "symbol": "SYNTHETIC", "rows": 1, "first_label": row[1], "last_label": row[1],
                "parsed_ohlcv_sha256": hashlib.sha256(
                    b"SYNTHETIC,2021-01-01T09:15:00,100.0,101.0,99.0,100.0,5.0\n").hexdigest()}]}
            try:
                self.assertTrue(pilot.verify_inputs(connection, audit, config)["all_source_row_hashes_verified"])
                connection.execute("UPDATE bars SET c=100.5")
                with self.assertRaisesRegex(ValueError, "audited rows"):
                    pilot.verify_inputs(connection, audit, config)
            finally:
                connection.close()


if __name__ == "__main__":
    unittest.main()
