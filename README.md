# Path-Robust Risk Controls for Intraday Mean Reversion in NSE Equities

MScFE 690 Capstone, WorldQuant University, Student Group 17838
Uchenna Splendor Ejike, Israel Olanrewaju Odeajo, Goodness Chibueze Kalu

## What this project does

We hold one intraday entry rule fixed and compare three ways of exiting it:

- **Time-only:** close after 15 minutes.
- **Stop-only:** close at a stop-loss, otherwise after 15 minutes.
- **Stop and target:** close at the first of a stop-loss or a profit target, otherwise after 15 minutes.

The entry buys a stock when its 15-minute return is unusually weak against the NIFTY 50 index (z-score of -2 or lower over the previous 20 sessions). The data are minute bars for RELIANCE, HDFCBANK, INFY, TCS and ITC from 2021 to 2023, split chronologically into development (60%), validation (20%) and a final test (20%).

**Main finding so far.** The entry signal earns 0.2200–0.6860 bp of reference capital per evaluable day before costs. The assumed fee takes 2.6063–2.6959 bp per day, so all three exits lose money. Adding a stop and target lowered the mean further, by 0.1273–0.6885 bp per day against time-only, while lowering expected shortfall and deepening funded drawdown. The [M7 results narrative](reports/m7_results/RESULTS.md) states that finding first and keeps the qualifications in one Limitations section. The final test (26 May to 29 December 2023) has not been evaluated yet.

## Submission documents

| Document | Location |
| --- | --- |
| M7 results narrative | [reports/m7_results/RESULTS.md](reports/m7_results/RESULTS.md) |
| Final project report (M7) | Pending |
| Solution design document (M7) | Pending |
| Presentation (M7) | Pending |
| M6 draft report | [PDF](reports/m6_draft/WQU_MScFE690_M6_Draft_Project_Group17838_LaTeX.pdf), [LaTeX](reports/m6_draft/WQU_MScFE690_M6_Draft_Project_Group17838_LaTeX.tex) |
| M6 response to peer review | [PDF](reports/m6_peer_review_response/Group17838_M6_Response_to_Peer_Review.pdf), [LaTeX](reports/m6_peer_review_response/Group17838_M6_Response_to_Peer_Review.tex) |
| M5 peer review received | [PDF](reports/m5_peer_review/Group17838_M5_Peer_Review_of_M4.pdf) |

## Run it

### Option 1: Google Colab (recommended)

1. [Open the M7 notebook in Colab](https://colab.research.google.com/github/I-am-Uchenna/nse-intraday-risk-controls/blob/main/notebooks/NSE_Intraday_M7.ipynb) and save a copy to your Drive.
2. Add My Drive shortcuts to the instructor folders **NSE Cash Stocks Data** and **NSE Index Data**.
3. In the first code cell set `CASH_FOLDER`, `INDEX_FOLDER` and `SAVE_FOLDER`. Leave `RUN_STAGE = "validation"`.
4. Choose **Runtime > Run all** on a CPU runtime and allow Drive access.
5. Compare the exported tables with [results/m7_validation_20261111](results/m7_validation_20261111/). They should match exactly.
6. Runs are saved only to `SAVE_FOLDER`. When the group is satisfied with one, tick `PUBLISH_RUN` in the publish cell near the end and rerun that cell to prepare its `results/` folder.

Full instructions, including the protocol freeze and the one-time final-test run, are in the [M7 guide](docs/M7_README.md).

### Option 2: local machine

Requires Python 3.10 or newer. Archive reading also needs `bsdtar` (`sudo apt install libarchive-tools` on Linux or WSL).

```bash
git clone https://github.com/I-am-Uchenna/nse-intraday-risk-controls.git
cd nse-intraday-risk-controls
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m unittest discover -s tests -v
```

`pip install -r requirements.txt` also installs this repository's `path_robust` package, so the tests and scripts run from any folder. The tests use synthetic data and the saved aggregate results, so they run without the instructor data. To re-run the market experiment locally:

1. Copy the instructor folders **NSE Cash Stocks Data** and **NSE Index Data** into `data/` (git ignores everything there). Yearly 7z, monthly RAR or extracted CSV layouts all work, as long as each month has only one.
2. Open `notebooks/NSE_Intraday_M7.ipynb` in VS Code or Jupyter and run all cells, keeping the default folder paths. The first cell detects that it is not in Colab, uses `data/`, shows a setup checklist and saves runs to `data/m7_runs/`, which is not tracked. The source check then shows which file each month will use before anything is loaded.
3. When the group is satisfied with a run, tick `PUBLISH_RUN` in the publish cell and rerun that cell. It writes `results/m7_<stage>_<YYYYMMDD>/` with checksums and a README, ready to commit, and never overwrites an existing folder.

The notebook is the only thing needed to run the study; nothing outside it is called.

## Where each result comes from

| Report tables (M6 draft) | Stage | Saved outputs |
| --- | --- | --- |
| Tables 5 to 7 | Q1 2021 pilot | [results/m4_pilot](results/m4_pilot/) |
| Tables 8 to 10, Figure 1 | Development, Jan 2021 to Oct 2022 | [results/development_20261001](results/development_20261001/) |
| Tables 11 and 12 | Validation, Oct 2022 to May 2023 | [results/validation_20261018](results/validation_20261018/) |
| Tables 13 to 16 | Peer-review diagnostics | [results/peer_review_20261022](results/peer_review_20261022/) |
| Reproduction check | Validation rerun with the M7 notebook | [results/m7_validation_20261111](results/m7_validation_20261111/) |

Each results folder has a `SHA256SUMS.txt` and a run manifest recording the code, data fingerprint and settings used. See the [results index](results/README.md).

## Repository layout

```text
notebooks/   Research notebooks. NSE_Intraday_M7.ipynb is the current version.
src/         path_robust package: execution engine, data parsing, signals, accounting,
             and paths.py, the single list of repository locations
scripts/     Command-line pilot (M4) and helpers that rebuild tables from saved results
tests/       Automated checks for the engine, the notebooks and the saved tables
config/      Study settings fixed before each stage was run
examples/    Small synthetic price data for the tests
results/     Saved aggregate outputs, one folder per run
reports/     Submitted reports, peer review and response
docs/        Module guides, methods and pipeline notes
data/        Placeholder only; instructor market data are not redistributed
```

The [repository guide](docs/REPOSITORY_GUIDE.md) describes every folder and file and defines the columns of each results table.

## Notebooks

| Notebook | Module | Purpose |
| --- | --- | --- |
| [NSE_Intraday_M7.ipynb](notebooks/NSE_Intraday_M7.ipynb) | M7 | Final notebook: full experiment plus protocol freeze and one-time final-test access |
| [NSE_Intraday_M6.ipynb](notebooks/NSE_Intraday_M6.ipynb) | M6 | Validation run and peer-review diagnostics ([guide](docs/M6_README.md)) |
| [NSE_Intraday_M4_Research.ipynb](notebooks/NSE_Intraday_M4_Research.ipynb) | M4 | Standalone research notebook used for the development run ([guide](docs/M4_README.md)) |
| [NSE_Intraday_M4_Launcher.ipynb](notebooks/NSE_Intraday_M4_Launcher.ipynb) | M4 | Five-step Colab launcher for the frozen Q1 2021 pilot |

Each notebook contains all of its research code and does not depend on `src/`. The `src/` package is the original M3/M4 implementation, still tested and used by `scripts/`. Method details: [METHODS.md](docs/METHODS.md); pipeline history: [PIPELINE.md](docs/PIPELINE.md).

## Data

The minute data were supplied by the course instructor and are not included here. Notebooks read the original archives without modifying them; set their locations in the notebook's first code cell. The command-line scripts keep local work files under `data/`, or under the folder named by the `NSE_DATA_DIR` environment variable if it is set. All repository locations are defined once in [src/path_robust/paths.py](src/path_robust/paths.py). See [data/README.md](data/README.md).

## Earlier file locations

The repository was reorganised on 11 November 2026. Links in the M6 draft PDF use the earlier layout, which is preserved at [commit 1a9ab7a](https://github.com/I-am-Uchenna/nse-intraday-risk-controls/tree/1a9ab7ae2418ec6e2beea533c63b4d476cc70439). Verification records inside `results/` also refer to the file names in use when they were created.

## Contributors

See [CONTRIBUTORS.md](CONTRIBUTORS.md).
