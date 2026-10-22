"""Check fee arithmetic, corruption rejection and the final-stage reading boundary."""
import ast
from copy import deepcopy
import csv
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("peer_diagnostics", ROOT/"scripts/peer_review_diagnostics.py")
diagnostics = importlib.util.module_from_spec(spec)
spec.loader.exec_module(diagnostics)


def fixture():
    means, episodes, es, statuses = [], [], [], []
    for label in ("start", "end"):
        episodes.append(dict(timestamp_label=label, unique_episodes=2))
        statuses.append(dict(timestamp_label=label, setting="reference", accounting="independent",
                             status="EVALUABLE", scheduled_days=2))
        statuses.append(dict(timestamp_label=label, setting="reference", accounting="funded",
                             status="EVALUABLE", scheduled_days=2))
        for policy in ("time_only", "stop_only", "stop_and_target"):
            for name, cost in (("reference",15),("cost_5",5),("cost_25",25)):
                means.append(dict(timestamp_label=label,setting=name,policy=policy,path="O-L-H-C",
                                  evaluable_days=2,mean_daily_pnl_bp=1-.1*cost))
            es.append(dict(timestamp_label=label, policy=policy,path="O-L-H-C",n_days=2,
                           tail_mass_days=.05,ES975_loss_bp=2,leave_one_day_out_min_bp=1,
                           leave_one_day_out_max_bp=2))
    return [means, episodes, es, statuses,
            [dict(stage="validation",scheduled_sessions=2)], []]


class PeerDiagnosticsTests(unittest.TestCase):
    def test_fee_decomposition_has_distinct_daily_trade_and_rupee_units(self):
        out = diagnostics.peer_review_tables("validation", *fixture())
        row = out["gross_net_returns"][0]
        self.assertAlmostEqual(row["gross_bp_per_day"], 1.)
        self.assertAlmostEqual(row["gross_bp_per_trade"], 10.)
        self.assertAlmostEqual(row["fee_bp_per_day"], 1.5)
        self.assertAlmostEqual(row["net_inr_per_day"], -5.)
        self.assertEqual(out["sample_accounting"][0]["primary_unavailable_days"], 0)

    def test_cost_or_sample_mismatch_is_rejected(self):
        args = fixture()
        args[0][1]["mean_daily_pnl_bp"] += 1
        with self.assertRaisesRegex(ValueError,"Inconsistent matched"):
            diagnostics.peer_review_tables("validation", *args)
        args = fixture()
        args[0][0]["evaluable_days"] = 3
        with self.assertRaisesRegex(ValueError,"Inconsistent matched"):
            diagnostics.peer_review_tables("validation", *args)

    def test_final_identity_rejected_before_any_result_csv_is_opened(self):
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)/"final"; folder.mkdir()
            (folder/"run_manifest.json").write_text('{"stage":"final"}',encoding="utf-8")
            with self.assertRaisesRegex(ValueError,"final results must not be read"):
                diagnostics.derive(folder, folder, Path(d)/"new")
        with self.assertRaisesRegex(ValueError,"Final-stage"):
            diagnostics.peer_review_tables("final", *fixture())

    def test_notebook_uses_same_function_and_saved_aggregates_reproduce(self):
        notebook = json.loads((ROOT/"NSE_Intraday_M6.ipynb").read_text(encoding="utf-8"))
        cell = next(c for c in notebook["cells"] if c["id"] == "m6-peer-review-diagnostics")
        source = "".join(cell["source"])
        fn = next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef))
        script = (ROOT/"scripts/peer_review_diagnostics.py").read_text(encoding="utf-8")
        original = next(n for n in ast.parse(script).body if isinstance(n,ast.FunctionDef))
        self.assertEqual(ast.dump(fn),ast.dump(original))
        with tempfile.TemporaryDirectory() as d:
            out = diagnostics.derive(ROOT/"results/development_20261001",
                                     ROOT/"results/validation_20261018",Path(d)/"out")
            self.assertEqual(len(out["gross_net_returns"]),12)
            self.assertEqual(len(out["execution_sensitivity"]),84)
            row = next(r for r in out["gross_net_returns"] if r["stage"]=="validation"
                       and r["timestamp_label"]=="start" and r["policy"]=="time_only")
            self.assertAlmostEqual(row["gross_bp_per_trade"],3.8166660268993877)
            for name in out:
                actual = (Path(d)/"out"/(name+".csv")).read_bytes()
                self.assertEqual(actual,(ROOT/"results/peer_review_20261022"/(name+".csv")).read_bytes())
            with self.assertRaises(FileExistsError):
                diagnostics.derive(ROOT/"results/development_20261001",
                                   ROOT/"results/validation_20261018",Path(d)/"out")


if __name__ == "__main__":
    unittest.main()
