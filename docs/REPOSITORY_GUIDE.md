# Repository guide and data dictionary

This guide lists every folder in the repository, what each file is for, which step of the study created it, and what the columns of the saved result tables mean. The [README](../README.md) explains how to run the study; this page explains what you are looking at.

## How files move through the repository

```text
data/  (private, ignored by git)            results/  (public, tracked)
  NSE Cash Stocks Data/   --+
  NSE Index Data/         --+--> notebook --> data/m7_runs/<RUN_ID>/ --(publish cell)--> results/m7_<stage>_<YYYYMMDD>/
                              (M7)            data/m7_runs/<RUN_ID>_research_outputs.zip
                                              data/m7_runs/m7_protocol_freeze.json
                                              data/m7_runs/m7_final_access.json
```

(The arrow from `data/m7_runs/` to `results/` is the notebook's publish cell, section 13a.)

1. The instructor archives sit in `data/` (or a Drive folder in Colab) and are never modified.
2. The M7 notebook reads them, runs one stage and saves the run to its save folder: `data/m7_runs/` locally, `SAVE_FOLDER` in Colab. Every run gets its own `RUN_ID` folder and ZIP. The freeze and final-access records sit beside them, outside any run folder, so that later runs can find them.
3. Nothing in the save folder is tracked. A run becomes public only when the group is satisfied with it and someone ticks `PUBLISH_RUN` in the notebook's publish cell and reruns that cell, which copies the run into `results/` in the convention below. Failed attempts, test runs and the freeze and access records therefore never land in a tracked folder by accident.

The notebook is the only thing needed to run the study. It calls nothing outside itself, so it runs unchanged in Colab and locally. The scripts in `scripts/` belong to earlier modules or build report text from saved tables; none of them is part of an M7 run.

## Naming and storage conventions

| Convention | Rule |
| --- | --- |
| Result folders | `<stage>_<YYYYMMDD>`, dated by run completion. M7 runs use `m7_validation_<date>` and `m7_final_<date>`. Earlier folders keep their original names. A second run on the same day gets a `b` suffix; folders are never overwritten. |
| Run identity | `RUN_ID` is `<UTC timestamp>-<work folder suffix>`, for example `20261111T081528Z-fzxevfhy`. It appears in `run_manifest.json`, the HTML report and the published README. |
| Checksums | Every published folder has `SHA256SUMS.txt` in `sha256  filename` form. Check one with `sha256sum -c SHA256SUMS.txt` inside the folder (Linux, WSL, macOS with `shasum -a 256 -c`). |
| Line endings | The notebooks, the archived M6 reports and every published result folder are stored with `-text` in `.gitattributes`, so git never rewrites their bytes and checksums stay valid on Windows, macOS and Linux. |
| Private data | Raw prices, SQLite databases, trade ledgers, cash ledgers and executed notebooks are excluded by `.gitignore` and refused by the publish cell. Only aggregate tables are public. |
| Locations | Every script and test finds files through [`src/path_robust/paths.py`](../src/path_robust/paths.py). Set `NSE_DATA_DIR` to keep data outside the repository. |

## Top level

| File | Purpose |
| --- | --- |
| `README.md` | Project summary, run instructions, links to results and reports. |
| `CONTRIBUTORS.md` | Group members and research workstreams. |
| `pyproject.toml` | Declares the `path_robust` package so `pip install -e .` makes it importable from anywhere. |
| `requirements.txt` | Installs the notebook packages and this repository's package (`-e .`). Use this one. |
| `requirements-notebook.txt` | NumPy, pandas, Matplotlib and the Jupyter tools the notebook needs. Colab already has them. |
| `.gitignore` | Keeps data, databases, archives, ledgers and build files out of git. Result CSVs are allowed only inside named results folders. |
| `.gitattributes` | Marks files whose exact bytes must not change (notebooks, archived reports, results). |

## notebooks/

Each notebook contains all of its own research code and does not import `src/`.

| File | Module | Purpose |
| --- | --- | --- |
| `NSE_Intraday_M7.ipynb` | M7 | Current notebook. Full experiment, source checks, declared 23 June 2023 amendment, protocol freeze from a reviewed validation run, the one-time final-test run, and the publish cell that copies a reviewed run into `results/`. Works in Colab or locally. |
| `NSE_Intraday_M6.ipynb` | M6 | Validation run and peer-review diagnostics. Kept unchanged; its code cells are the reference the M7 tests compare against. |
| `NSE_Intraday_M4_Research.ipynb` | M4 | Standalone notebook that produced the development run. |
| `NSE_Intraday_M4_Launcher.ipynb` | M4 | Five-step Colab launcher for the frozen Q1 2021 command-line pilot. |

## src/path_robust/

The original M3 and M4 implementation as an installable package. Used by `scripts/` and `tests/`; the notebooks carry their own copies of the logic.

| File | Purpose |
| --- | --- |
| `paths.py` | The single list of repository locations (`ROOT`, `DATA`, `RESULTS`, `RUN[...]`, `NOTEBOOK[...]`, `REPORT[...]`). |
| `data.py` | Strict schema for one instrument's minute bars (`symbol,timestamp,open,high,low,close`). Rejects unordered or invalid rows. |
| `vendor.py` | Streaming parser for the instructor CSV layout (`<ticker>,<date>,<time>,<open>,<high>,<low>,<close>,<volume>`). Rejects rather than repairs. |
| `engine.py` | Long-only minute-bar execution: entry, stop, target and time exits under a declared intrabar path. |
| `research.py` | Past-only signal, fixed-capital daily accounts and the trading calendar logic. |
| `fixtures.py` | Hand-built synthetic cases for the tests. Not market data. |

## scripts/

None of these is needed to run M7. All are Python and run the same way on Windows, macOS and Linux.

| File | When to use it | Writes |
| --- | --- | --- |
| `m7_results_narrative.py` | Rebuilds the M7 results note from saved development and validation tables. | `reports/m7_results/RESULTS.md`. |
| `prepare_pilot.py` | M4 pilot: stages selected archive members into a private SQLite database. | `data/m4_pilot/` (private). |
| `run_pilot.py` | M4 pilot: replays the frozen Q1 2021 protocol from that database. | `results/m4_pilot/` aggregates. |
| `run_limited.py` | Runs a command under a Windows memory cap (used for the M4 pilot). | A resource report. |
| `summarize_m6.py` | Builds the M6 development-versus-validation tables from saved aggregates. | `results/m6_comparison_20261018/`. |
| `peer_review_diagnostics.py` | Builds the gross/net, sample, execution and ES sensitivity tables from saved aggregates. | `results/peer_review_20261022/`. |
| `run_examples.py` | Regenerates the synthetic M3 examples. | `results/synthetic_*`. |
| `run_checks.py` | Runs the unit tests, then `run_examples.py`. | `results/checks.json`. |

## tests/

Run all of them with `python -m unittest discover -s tests`. They use synthetic data and the saved aggregate tables, never instructor prices or final-test outcomes.

| File | What it checks |
| --- | --- |
| `test_data.py`, `test_vendor.py` | CSV schemas, timestamp handling and rejection of bad rows. |
| `test_engine.py` | Exit mechanics, including bars where stop and target are both touched. |
| `test_research.py` | Signals, daily accounts, calendar and risk metrics. |
| `test_pilot.py`, `test_prepare.py` | M4 pilot denominators, provenance and archive staging. |
| `test_notebook.py`, `test_m6_notebook.py` | The M4 and M6 notebook code on synthetic records. |
| `test_m6_summary.py`, `test_peer_review_diagnostics.py` | The M6 and peer-review table builders. |
| `test_m7_notebook.py` | M7 controls: stage gate, freeze, final access, code fingerprint, cells unchanged from M6. |
| `test_m7_source_amendment.py` | The 23 June 2023 amendment: merge, pruning, quality gates and refusals. |
| `test_m7_publish.py` | The notebook's publish cell: byte-for-byte copies, refusal of private or incomplete runs, no overwrites, the Colab ZIP. |
| `test_m7_narrative.py` | The M7 results note builder. |

## config/

Settings recorded before each stage was run. Changing them would change the protocol fingerprint.

| File | Purpose |
| --- | --- |
| `reference_protocol.json` | The fixed experiment: three exits, signal window, z threshold, barrier multipliers, holding cap, costs and sensitivity settings. |
| `m4_pilot.json` | The frozen Q1 2021 pilot: universe, dates, holidays, excluded sessions, timestamp assumptions, capital. |
| `m6_validation_plan.json` | The chronological split and the validation plan, recorded before validation was run. |
| `m7_source_amendment.md` | Record of amendment `M7-A1-2023-06-23`: the finding, the rule, the quality gates and its effect on earlier stages. |

## examples/

| File | Purpose |
| --- | --- |
| `synthetic_bars.csv` | A few synthetic minute bars in the canonical schema. |
| `synthetic_episodes.json` | Hand-built trade episodes, each labelled `SYNTHETIC / NOT MARKET DATA`, used to show how the exits can rank differently on the same bars. |

## data/

Only `data/README.md` is tracked. Everything else is private.

| Path | Contents |
| --- | --- |
| `data/README.md` | Data-handling rules: archives stay unchanged, no filling, no redistribution. |
| `data/NSE Cash Stocks Data/` | Instructor monthly cash archives (`Cash Data <Month> <Year>.rar`) and the June 2023 supplement. |
| `data/NSE Index Data/` | Instructor index archives (yearly `NSE-Index-YYYY.7z` or monthly RAR). |
| `data/m7_runs/` | Local notebook save folder: one folder and ZIP per run, plus `m7_protocol_freeze.json` and `m7_final_access.json`. |
| `data/m4_pilot/` | Private SQLite database and ledgers from the M4 pilot. |

## reports/

| Folder | Contents |
| --- | --- |
| `m5_peer_review/` | Our M5 review of another group's M4 report. |
| `m6_draft/` | The M6 draft report, PDF and LaTeX source, kept byte-identical. |
| `m6_peer_review_response/` | Our response to the peer review of M6, PDF and LaTeX source. |
| `m7_results/` | The M7 results note (`RESULTS.md`), generated from saved tables by `scripts/m7_results_narrative.py`. |

The M7 final report and the one-page solution design document are added here when they are submitted.

## docs/

| File | Purpose |
| --- | --- |
| `REPOSITORY_GUIDE.md` | This page. |
| `M7_README.md` | Step-by-step M7 run guide: validation, freeze, final access, local runs, the source amendment. |
| `M6_README.md` | M6 guide, kept byte-identical to its recorded checksum, so its links use the pre-November layout. |
| `M4_README.md` | M4 notebook and pilot guide. |
| `METHODS.md` | Implemented research and execution rules from M3/M4. |
| `PIPELINE.md` | History of the command-line pilot and what the notebooks added. |

## results/

One folder per run or derived table set. See also the [results index](../results/README.md).

| Folder | Stage | Created by |
| --- | --- | --- |
| files directly in `results/` | M3 synthetic examples and M4 verification records | `run_examples.py`, `run_checks.py`, notebook verification |
| `m4_pilot/` | Q1 2021 pilot | `run_pilot.py` |
| `development_20261001/` | Development, 1 Jan 2021 to 17 Oct 2022 | M4 research notebook |
| `validation_20261018/` | Validation, 18 Oct 2022 to 25 May 2023 | M6 notebook |
| `m6_comparison_20261018/` | Development against validation | `summarize_m6.py` |
| `peer_review_20261022/` | Gross/net, sample and sensitivity tables | `peer_review_diagnostics.py` |
| `m6_verification/` | Checks of the M6 package | verification records |
| `m7_validation_20261111/` | Validation reproduced with the M7 notebook | M7 notebook, published by hand before the publish cell existed |
| `m7_final_<date>/` | Final test, 26 May to 29 Dec 2023 (after the one approved run) | M7 notebook publish cell |

### Files in a published M7 run folder

| File | Contents |
| --- | --- |
| `run_manifest.json` | Run ID, stage, completion time, protocol SHA-256, scientific settings, notebook code SHA-256, Python and package versions, source status, final-access record. |
| `input_audit.json` | Source files read, their checksums and member names, coverage, excluded supplements and declared amendments. Account-specific paths are reduced to file names. |
| `conclusions.md` | The notebook's written interpretation of the run. |
| `research_report.html` | Single-page report with the main tables and every figure embedded. |
| `*.csv` | The aggregate tables defined below. |
| `*.png` | Figures: calendar split, coverage, paired effects, funded equity and drawdown, execution sensitivity, synthetic ambiguity. |
| `protocol_freeze.json`, `final_access.json` | Final runs only: the validation freeze checked before the run, and the access record written before evaluation. |
| `runtime-requirements.txt` | Exact package versions recorded by the run. |
| `README.md` | What the run is and which file to read first. |
| `SHA256SUMS.txt`, `.gitattributes` | Checksums and the byte-preservation rule. |
| `verification.json` | Present only where the run was independently compared with earlier results (for example `m7_validation_20261111`). |

## Result table dictionary

### Shared columns

These appear in many tables and always mean the same thing.

| Column | Meaning |
| --- | --- |
| `stage` | `development`, `validation` or `final`. Stages are never pooled. |
| `timestamp_label` | How a source minute label is read: `start` (the label is the minute's start) or `end` (its end). Both are reported because the source does not say. |
| `path` | Assumed order of prices inside a minute bar when a stop and a target could both be hit: `O-H-L-C` (high before low) or `O-L-H-C` (low before high). |
| `policy` | Exit rule: `time_only`, `stop_only` or `stop_and_target`. |
| `contrast` | Paired difference between two exits on the same days: `combined_minus_time`, `stop_minus_time` or `combined_minus_stop`. |
| `setting` | Execution assumption. `reference` is 15 bp round trip, 1-minute entry delay, no extra stop slippage. `cost_5` and `cost_25` change the round-trip cost; `stop_slippage_5` and `stop_slippage_10` add slippage on stop exits; `delay_2` and `delay_5` delay entry. |
| `n_days`, `evaluable_days`, `aligned_days`, `primary_days` | Number of trading days in the calculation. Paired tables use only days evaluable for every exit compared. |
| `_bp` suffix | Basis points of the fixed reference capital per day, unless the name says per trade. |
| `status` | Day status (`EVALUABLE` and the reasons a day is not) or interval status (`AVAILABLE` or `UNAVAILABLE` with the reason). |

### Per-table columns

| Table | Row is | Other columns |
| --- | --- | --- |
| `calendar_split.csv` | One stage | `start`, `end`, `scheduled_sessions`. |
| `coverage_monthly.csv` | One symbol in one month | `rows` (minute rows read), `observed_days`, `first_label`, `last_label` (earliest and latest raw time labels). |
| `coverage_daily.csv` | One symbol on one day, per timestamp reading | `observed_minutes` inside the 375-minute session. |
| `status_counts.csv` | Setting, accounting and day status | `accounting` (`funded`: one capital account carried through the stage; `independent`: each day funded afresh), `scheduled_days` with that status. |
| `sample_accounting.csv` | Stage and timestamp reading | `scheduled_days`, `primary_evaluable_days`, `primary_unavailable_days`, `explicitly_excluded_days`, `incomplete_candidate_days`, `funded_identified_days`, `reference_unique_episodes` (trades under the reference setting), `mean_episodes_per_primary_day`. |
| `policy_means.csv` | Setting, exit and path | `mean_daily_pnl_bp` (net mean daily P&L), `daily_sd_bp` (its standard deviation across days). |
| `gross_net_returns.csv` | Stage, timestamp reading and exit | `unique_episodes`, `entry_fraction_of_capital` (0.1 means INR 10,000 per trade on INR 100,000), `gross_bp_per_day`, `fee_bp_per_day`, `net_bp_per_day` (gross minus fees), `gross_bp_per_trade`, `gross_inr_per_day`, `net_inr_per_day`, `reference_round_trip_fee_bp`. |
| `paired_effects.csv` | Setting, path and contrast | `mean_difference_bp`: mean of the daily differences between the two exits. The primary result is `combined_minus_time` under `reference`. |
| `intervals.csv` | Path, contrast and block length | Moving-block bootstrap interval for the paired mean: `mean_difference_bp`, `block_length` (days), `segment_lengths` (lengths of the contiguous runs of evaluable days), `support_blocks`, `lower_bp`, `upper_bp`, `status`. Intervals are exploratory. |
| `aligned_sensitivity.csv`, `execution_sensitivity.csv` | Setting and contrast | On days evaluable under both settings: `reference_difference_bp`, `scenario_difference_bp`, `change_from_reference_bp`. |
| `expected_shortfall.csv` | Path and exit | `ES975_loss_bp`: average loss in the worst 2.5% of days; `tail_mass_days` (2.5% of `n_days`, may be fractional); `leave_one_day_out_min_bp` and `_max_bp`: the range of ES when each day is dropped in turn. |
| `expected_shortfall_sensitivity.csv` | Stage, timestamp reading and exit | The `expected_shortfall.csv` measures with a `stage` column and one row per exit, as used in the peer-review response. In this sample the two paths give the same ES. |
| `tail_dates.csv` | One tail day | `date`, `loss_bp`, `tail_weight_days` (share of the day in the tail, 1 or a fraction). |
| `funded_drawdown.csv` | Funded segment, exit and path | `max_drawdown_pct` from minute-marked equity, `saved_marks`, `first_date`, `last_date`, `daily_close_max_drawdown_pct` from daily closes only, `identified_daily_closes`, `last_identified_daily_close`, `segment_initial_capital` (INR). |
| `exit_ambiguity.csv` | Timestamp reading | `unique_episodes`, `ambiguous_episodes` (trades where one bar touched both stop and target, so the path assumption decides), `ambiguity_rate`. |
| `ledger_reconciliation.csv` | Timestamp reading and setting | Independent recomputation of the trade and cash ledgers: `resolved_trade_rows`, `evaluated_account_days`, `matched_six_account_days` (3 exits by 2 paths), `maximum_trade_error_inr`, `maximum_daily_error_inr`, `maximum_cash_error_inr`, `tolerance_inr`, `status`, `scope`. |
| `bootstrap_reliability.csv` | Timestamp reading and simulated autocorrelation `phi` | Development only; the file is empty in later stages. Simulated coverage of the interval method on the real calendar: `replications`, `bootstrap_repetitions`, `block_length`, `coverage_pct` and `coverage_mcse_pp`, `rejection_pct` and `rejection_mcse_pp`, `mean_width_bp`, `median_width_bp`, `gaussian_oracle_width_bp`, `mean_width_over_oracle`, `status`. |

### Older tables

| Table | Folder | Columns |
| --- | --- | --- |
| `scenario_means.csv`, `paired_contrasts.csv`, `sensitivity_comparisons.csv`, `run_diagnostics.csv` | `m4_pilot/` | The pilot's equivalents of policy means, paired effects, sensitivity and day status. `timestamp_assumption` there is the same idea as `timestamp_label`; `common_days` is `n_days`. |
| `comparison.csv` | `m6_comparison_20261018/` | Per stage and exit: `mean_daily_pnl_bp`, `policy_minus_time_bp`, `ES975_loss_bp`, `tail_mass_days`. |
| `sensitivity.csv` | `m6_comparison_20261018/` | `aligned_sensitivity.csv` for both stages, with a `stage` column. |
| `synthetic_examples.csv`, `synthetic_comparisons.csv` | `results/` | M3 hand-built cases: one row per trade under each exit, and the resulting exit comparisons. Labelled synthetic. |
