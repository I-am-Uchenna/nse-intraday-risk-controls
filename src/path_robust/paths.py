"""Single source of truth for repository locations.

Every script and test resolves files through this module, so the layout can
change in one place and commands work from any working directory.
Set NSE_DATA_DIR to keep local market-data work files outside the repository.
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

SRC = ROOT / "src"
NOTEBOOKS = ROOT / "notebooks"
SCRIPTS = ROOT / "scripts"
TESTS = ROOT / "tests"
CONFIG = ROOT / "config"
EXAMPLES = ROOT / "examples"
RESULTS = ROOT / "results"
REPORTS = ROOT / "reports"
DOCS = ROOT / "docs"
DATA = Path(os.environ.get("NSE_DATA_DIR", ROOT / "data")).expanduser().resolve()

NOTEBOOK = {
    "M4_LAUNCHER": NOTEBOOKS / "NSE_Intraday_M4_Launcher.ipynb",
    "M4_RESEARCH": NOTEBOOKS / "NSE_Intraday_M4_Research.ipynb",
    "M6": NOTEBOOKS / "NSE_Intraday_M6.ipynb",
    "M7": NOTEBOOKS / "NSE_Intraday_M7.ipynb",
}

RUN = {
    "M4_PILOT": RESULTS / "m4_pilot",
    "DEVELOPMENT": RESULTS / "development_20261001",
    "VALIDATION": RESULTS / "validation_20261018",
    "M6_COMPARISON": RESULTS / "m6_comparison_20261018",
    "PEER_REVIEW": RESULTS / "peer_review_20261022",
    "M7_VALIDATION": RESULTS / "m7_validation_20261111",
}
