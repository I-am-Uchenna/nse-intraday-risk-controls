"""Run unit tests, then regenerate the labelled synthetic findings."""

import json
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from path_robust.paths import RESULTS, ROOT, SCRIPTS, TESTS  # noqa: E402


def main():
    suite = unittest.defaultTestLoader.discover(str(TESTS))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    output = RESULTS
    output.mkdir(exist_ok=True)
    (output / "checks.json").write_text(json.dumps({
        "data_label": "SYNTHETIC / NOT MARKET DATA",
        "tests_run": result.testsRun, "failures": len(result.failures),
        "errors": len(result.errors), "skipped": len(result.skipped),
        "successful": result.wasSuccessful(),
        "scope": "Synthetic execution, input-validation, past-only signal, fixed-capital account and sample-risk tests; no empirical validation.",
    }, indent=2) + "\n", encoding="utf-8")
    if not result.wasSuccessful():
        return 1
    return subprocess.run([sys.executable, str(SCRIPTS / "run_examples.py")],
                          cwd=ROOT, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
