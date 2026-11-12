"""The M7 results note must lead with the cost finding and park caveats in Limitations."""
import importlib.util
import unittest

from path_robust.paths import REPORT, RUN, SCRIPTS

spec = importlib.util.spec_from_file_location("m7_narrative", SCRIPTS / "m7_results_narrative.py")
narrative = importlib.util.module_from_spec(spec)
spec.loader.exec_module(narrative)

WITHDRAWN_BEFORE_LIMITATIONS = (
    "exploratory",
    "does not establish",
    "undercoverage",
    "not sufficient",
    "cannot",
)


def _flat(text):
    return " ".join(text.split())


def _tables():
    return narrative.load_tables(
        RUN["DEVELOPMENT"], RUN["VALIDATION"], RUN["PEER_REVIEW"], RUN["M7_VALIDATION"])


class M7NarrativeTests(unittest.TestCase):
    def test_headline_precedes_limitations_and_uses_saved_band(self):
        text = narrative.narrative_from_repository()
        flat = _flat(text)
        self.assertTrue(flat.startswith(
            "The entry signal earns 0.2200–0.6860 bp of reference capital per evaluable day before costs, "
            "against assumed fees of 2.6063–2.6959 bp per day. The fee exceeds that gross"))
        self.assertIn("three ways of losing money", flat)
        self.assertLess(flat.index("three ways of losing money"), flat.index("## Results"))
        self.assertLess(text.index("## Results"), text.index("## Limitations"))
        head, limitations = text.split("## Limitations", 1)
        folded_head = _flat(head).lower()
        folded_limits = _flat(limitations).lower()
        for phrase in WITHDRAWN_BEFORE_LIMITATIONS:
            self.assertNotIn(phrase, folded_head, phrase)
        for phrase in ("exploratory", "complete-case", "scenario", "expected shortfall",
                       "funded drawdown", "final partition", "shared worst day", "undercoverage"):
            self.assertIn(phrase, folded_limits, phrase)
        self.assertIn("| Development | start | Time-only | 360 | 0.3179 | 2.6542 | -2.3362 |", text)
        self.assertIn("| Validation | start | Stop and target | 148 | -0.0025 | 2.6959 | -2.6985 |", text)
        self.assertIn("final_test_evaluated as false", flat)

    def test_saved_file_matches_the_generator(self):
        saved = (REPORT["M7_RESULTS"] / "RESULTS.md").read_text(encoding="utf-8")
        self.assertEqual(saved.replace("\r\n", "\n"), narrative.narrative_from_repository())

    def test_a_non_negative_net_refuses_the_headline(self):
        tables = _tables()
        gross = [dict(row) for row in tables["gross"]]
        gross[0]["net_bp_per_day"] = "0.1000"
        gross[0]["gross_bp_per_day"] = str(float(gross[0]["fee_bp_per_day"]) + 0.1)
        with self.assertRaisesRegex(ValueError, "losing-money"):
            narrative.render_narrative(**{**tables, "gross": gross})

    def test_final_partition_record_is_rejected(self):
        tables = _tables()
        reproduction = {**tables["reproduction"], "final_test_evaluated": True}
        with self.assertRaisesRegex(ValueError, "Final-partition"):
            narrative.render_narrative(**{**tables, "reproduction": reproduction})


if __name__ == "__main__":
    unittest.main()
