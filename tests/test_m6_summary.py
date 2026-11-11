"""Synthetic aggregate fixtures: these are not validation market findings."""

import csv
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

from path_robust.paths import SCRIPTS
SCRIPT = SCRIPTS / "summarize_m6.py"
spec = importlib.util.spec_from_file_location("summarize_m6", SCRIPT)
summary = importlib.util.module_from_spec(spec)
spec.loader.exec_module(summary)


def write_csv(folder, name, rows):
    with (folder / f"{name}.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def fixture(folder, stage):
    folder.mkdir()
    (folder / "run_manifest.json").write_text(json.dumps(dict(stage=stage, run_id=f"synthetic-{stage}")))
    means, effects, es, ambiguity, funded, sensitivity = [], [], [], [], [], []
    values = dict(time_only=-1., stop_only=-2., stop_and_target=-1.5)
    for label in ("start", "end"):
        for policy, value in values.items():
            means.append(dict(timestamp_label=label, setting="reference", path=summary.PATH,
                policy=policy, evaluable_days=40, mean_daily_pnl_bp=value))
            es.append(dict(timestamp_label=label, path=summary.PATH, policy=policy,
                n_days=40, tail_mass_days=1., ES975_loss_bp=3.))
            for segment in (1, 2):
                funded.append(dict(timestamp_label=label, path=summary.PATH, policy=policy,
                    segment=segment, max_drawdown_pct=2., saved_marks=100,
                    daily_close_max_drawdown_pct=1., identified_daily_closes=25,
                    segment_initial_capital=100000., first_date="2021-01-01", last_date="2021-02-01"))
        ambiguity.append(dict(timestamp_label=label, unique_episodes=50, ambiguous_episodes=1, ambiguity_rate=.02))
        for contrast, (left, right) in summary.CONTRASTS.items():
            difference = values[left] - values[right]
            effects.append(dict(timestamp_label=label, setting="reference", path=summary.PATH,
                contrast=contrast, n_days=40, mean_difference_bp=difference))
            for setting in summary.SETTINGS:
                sensitivity.append(dict(timestamp_label=label, setting=setting, contrast=contrast,
                    aligned_days=40, reference_difference_bp=difference,
                    scenario_difference_bp=difference, change_from_reference_bp=0.))
    for name, rows in zip(("policy_means", "paired_effects", "expected_shortfall",
                          "exit_ambiguity", "funded_drawdown", "aligned_sensitivity"),
                         (means, effects, es, ambiguity, funded, sensitivity)):
        write_csv(folder, name, rows)


class SummaryTests(unittest.TestCase):
    def test_summary_keeps_stage_and_funded_segment_boundaries(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for stage in ("development", "validation"):
                fixture(root / stage, stage)
            result = summary.summarize(root / "development", root / "validation", root / "report")
            self.assertEqual(len(result["stages"]), 2)
            for stage in result["stages"]:
                self.assertEqual(len(stage["reference"]), 6)
                self.assertEqual(len(stage["funded_drawdown"]), 12)
                self.assertEqual(len(stage["sensitivity"]), 42)
                self.assertEqual(stage["reference"][2]["policy_minus_time_bp"], -.5)
                self.assertEqual(len(stage["source_sha256"]), 7)
            self.assertTrue((root / "report" / "comparison.csv").is_file())
            with self.assertRaises(FileExistsError):
                summary.summarize(root / "development", root / "validation", root / "report")
            with self.assertRaises(ValueError):
                summary.summarize(root / "development", root / "validation", root / "development" / "new")

    def test_rejects_inconsistent_effect_and_final_before_reading_csvs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture(root / "validation", "validation")
            path = root / "validation" / "paired_effects.csv"
            with path.open(newline="", encoding="utf-8") as stream:
                rows = list(csv.DictReader(stream))
            rows[0]["mean_difference_bp"] = "99"
            write_csv(path.parent, "paired_effects", rows)
            with self.assertRaisesRegex(ValueError, "combined_minus_time"):
                summary.read_stage(path.parent, "validation")
            final = root / "final"
            final.mkdir()
            (final / "run_manifest.json").write_text('{"stage":"final"}')
            with self.assertRaisesRegex(ValueError, "final-stage"):
                summary.read_stage(final, "validation")


if __name__ == "__main__":
    unittest.main()
