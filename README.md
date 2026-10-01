# Path-Robust Risk Controls for Intraday Mean Reversion in NSE Equities

Student Group 17838 | MScFE 690 Capstone

This study compares three exit policies for the same long-only intraday entries:
**time-only, stop-only with the same time cap, and combined stop-loss and
profit-target exits with that time cap**. The question is whether risk controls
improve returns after costs or reduce downside risk, and whether the comparison
survives conservative assumptions about execution. A target-only strategy is
outside the submitted scope.

## Implementation and evidence

The M3 execution component applies the three policies to predetermined episodes
under O-L-H-C and O-H-L-C candle paths. Its checked-in example results are entirely
synthetic. They test event ordering and arithmetic; they are not market results.

The M4 development pipeline adds a streaming vendor-data adapter, selected-file
audits, past-only stock-minus-index signals, fixed-notional allocation and
independent session cash accounts. It processes a bounded January–March 2021
sample under a protocol declared before the first strategy replay. The five
predeclared examples are RELIANCE, HDFCBANK, INFY, TCS and ITC, with .NSEI as the
signal benchmark. They are not a performance-selected or representative NSE
universe, and the index is not traded as a hedge.

The development replay is conditional on timestamp and fill assumptions. It is
not an out-of-sample test, a parameter search or a continuously funded portfolio.
It does not construct minute-by-minute marked-to-market equity, establish
maximum drawdown, validate real fills or demonstrate a deployable trading edge.
See [methods](METHODS.md) and the [remaining work](PIPELINE.md).

## Complete research notebook (recommended)

[Open the research notebook in Colab](https://colab.research.google.com/github/I-am-Uchenna/nse-intraday-risk-controls/blob/main/NSE_Intraday_Research.ipynb).
Save a copy in Drive and run in a fresh hosted CPU runtime. All research code is
visible in the notebook: archive validation, chronological partitions, signals,
three-policy execution, cash ledgers, funded minute-close equity, drawdown,
expected shortfall, paired block intervals, sensitivity analysis and exports.
It does not clone this repository or invoke external research scripts.

The default stage is development on the planned 2021–2023 five-stock study.
The final stage requires a matching saved validation freeze. The original
instructor archives remain private and are accessed through Drive shortcuts.
Only selected CSVs are streamed, equity is streamed to disk, and original files
are never overwritten. Google Drive authorization must complete before ingestion.

The notebook was executed from a clean local kernel on the previously audited
Q1 2021 pilot: all 24 code cells completed, all 84 policy/scenario means matched
the published pilot, and the new accounting checks passed. This is verification
of the complete pipeline on development data, **not evidence that the full
2021–2023 study or mounted-Drive run has completed**. New funded/risk outputs are
separate diagnostics; the historical M4 reports remain unchanged.

The scientific Python packages used for tables and plots are preinstalled in
Colab. For local reproduction see `requirements-notebook.txt`. The underlying
historical M3/M4 command-line code below continues to use the standard library.
The earlier five-step launcher is retained as a historical convenience; it is
not the complete research deliverable.

## Earlier pilot launcher

[Open the notebook](https://colab.research.google.com/github/I-am-Uchenna/nse-intraday-risk-controls/blob/main/NSE_Capstone_Colab.ipynb), save a copy in Drive, then run its five steps.
It connects to the instructor folders through My Drive shortcuts, runs the checks
and frozen Q1 2021 pilot on Colab, displays tables and a labelled chart, and saves
aggregate outputs back to Drive. Only the two data-folder paths need configuring.
Use a CPU runtime; no local Python installation or Windows memory wrapper is needed.

The notebook pins `colab-v1` and records the executed commit. It reuses the tested
research modules rather than maintaining a second implementation. Source prices
stay private; temporary database/ledgers remain on the Colab VM. This is the
existing development pilot, not a completed full-period or final holdout study.
If the repository becomes private, its authentication must also be configured in
Colab. See [Google's runtime and Drive guidance](https://research.google.com/colaboratory/faq.html).

## Requirements

- Python **3.10 or newer**; the Python code uses only the standard library.
- Windows only for the optional `run_limited.py` memory wrapper.
- `bsdtar` (`libarchive-tools` on Colab/Linux) or Windows `tar`, with RAR/7z support.
  Python's standard-library `zipfile` reads the outer ZIP files.
- The separately supplied instructor archives and enough local disk space for
  selected archive containers and the private SQLite database.

`requirements.txt` describes the historical command-line implementation;
`requirements-notebook.txt` lists the standalone notebook dependencies.
Check that `python` resolves to an installed interpreter and `tar --version`
identifies a suitable archive reader. No market data are included in this
repository. Read [data handling](data/README.md) before preparing local inputs.

## Reproduce the synthetic checks

Run all commands from the repository root. In Windows PowerShell:

```powershell
python scripts/run_limited.py --memory-mib 384 --report data/checks_memory.json -- python scripts/run_checks.py
```

This runs the tests and regenerates `results/checks.json` and the labelled M3
synthetic examples. The final test count and pass/fail status are recorded in
`results/checks.json`; a passing test suite is not empirical validation.
To regenerate only the synthetic examples:

```powershell
python scripts/run_limited.py --memory-mib 384 --report data/examples_memory.json -- python scripts/run_examples.py
```

The wrapper applies a **384 MiB aggregate committed-memory limit** to the child
process tree, including archive-reader descendants, and runs it at idle priority.
This is not a strict resident-memory limit. The small supervising process is
outside the cap. Its JSON report records the observed peak, exit status and any
failure. A nonzero exit alone does not identify memory exhaustion.

## Prepare the private development sample

`config/m4_pilot.json` records the frozen pilot universe, dates, calendar handling,
source selection and execution scenarios. Keep this version intact; record any
later design change in a new version before evaluating its outcomes.
`config/reference_protocol.json` describes the full-study specification and its
remaining implementation work; `results/m4_pilot/run_manifest.json` identifies
the completed development replay.

Replace the path below with the directory containing the original downloads.
Preparation streams one selected CSV at a time into SQLite and records input
checksums and row diagnostics. It stages compressed nested containers on disk;
it does not unpack the entire archive collection or load it into memory.

```powershell
python scripts/run_limited.py --memory-mib 384 --report data/m4_pilot/prepare_memory.json -- python scripts/prepare_pilot.py --downloads "C:\path\to\downloaded_archives" --work-dir data/m4_pilot --config config/m4_pilot.json
```

Outer ZIP delivery filenames must match the frozen configuration's `raw_delivery_glob`.
Direct instructor RAR/7z files are also accepted. Repeat `--downloads` for separate
cash and index folders. The loader rejects duplicate matching sources.
The script creates `data/m4_pilot/pilot.sqlite` and
`data/m4_pilot/input_audit.json`. It refuses to overwrite an existing database;
use a new work directory for a new preparation run. The database and staged
archives remain private local files excluded from version control.

## Run the conditional market development replay

After preparation completes:

```powershell
python scripts/run_limited.py --memory-mib 384 --report data/m4_pilot/replay_memory.json -- python scripts/run_pilot.py --config config/m4_pilot.json --work-dir data/m4_pilot --output-dir results/m4_pilot
```

The runner checks the configuration hash and stored data against the preparation
audit, then reads the private database one session at a time. Aggregate outputs
are written separately from the private market ledgers:

| Location | Outputs |
| --- | --- |
| `results/m4_pilot/` | `summary.json`, `scenario_means.csv`, `paired_contrasts.csv`, `sensitivity_comparisons.csv`, `run_diagnostics.csv`. |
| `data/m4_pilot/` | `replay_ledgers.jsonl`, `daily_accounts.csv`; these contain restricted market detail and remain local. |

These generated results must be interpreted as conditional development evidence.
Use each run's configuration hash, input audit, exclusions and resource report
when reproducing or reviewing it.

The replay compares assumed start-labelled and end-labelled minutes; neither
case establishes the supplier's actual convention. Asia/Kolkata is also an
explicit assumption. Calendar sessions come from the declared calendar rather
than whichever days happen to appear in the files. The nonstandard session on
24 February 2021 is excluded from trading but retained as missing history.
That retrospective exclusion was declared before inspecting pilot P&L; it was
not a historically available trading decision, and outage-day losses are not
estimated. Missing windows are not replaced with older valid observations.

The reference scenario uses a one-minute entry delay, 15-minute holding cap and
15 bp round-trip cost. One-at-a-time checks use 5/25 bp common cost, 5/10 bp extra
stop slippage and 2/5-minute entry delay. Each uses all three policies and both
candle paths. These are declared research assumptions, not verified brokerage
charges or recovered price paths.

## M4 preliminary findings

All 14 declared runs completed. The 18 selected input files contain 137,036 rows;
the runner rechecked their ingestion hashes. The pilot has 20 common evaluable
sessions, 20 warmup sessions, one nonstandard exclusion and 20 later sessions
with incomplete prior history. The reference start/end interpretations have
33/24 episodes, respectively, and include 4/7 valid zero-trade days.

| Reference mean daily P&L / INR 100,000, in bp | Start labels | End labels |
| --- | ---: | ---: |
| Time-only | -2.914 | -0.886 |
| Stop-only | -2.734 | -1.359 |
| Stop and target | -3.476 | -1.957 |
| Combined minus time | -0.562 | -1.072 |

Reference costs are 15 bp per round trip with a one-minute entry delay. Both
intrabar paths coincide because **no ambiguous active dual-barrier episode occurs
in this pilot**. This is not evidence that ambiguity is unimportant elsewhere.
The start-label stop-only advantage of 0.180 bp becomes -0.220 bp with 5 bp extra
stop slippage. Some lower-cost/delay scenarios have positive time-only returns;
none establishes the correct timestamp interpretation or a deployable strategy.

See the [complete scenario summary](results/m4_pilot/summary.json),
[paired contrasts](results/m4_pilot/paired_contrasts.csv),
[source fingerprints](results/m4_pilot/run_manifest.json) and
[independent reconciliation](results/m4_pilot/independent_reconciliation.json).
The original M4 run passed 99 software checks; Colab support adds a source-staging check. The market replay peaked at 39.70 MiB of aggregate
child-process committed memory; this excludes its supervisor and OS file cache.

## Synthetic illustration from M3

**All prices and results in this table are SYNTHETIC / NOT MARKET DATA.**

A constructed episode enters at 100, sets a stop at 99 and a target at 101, and
has a scheduled exit 15 minutes later at 100.5. Its first candle contains both
barriers. At 15 bp round-trip cost:

| Assumed price order | Time-only net bp | Stop-only net bp | Combined net bp |
| --- | ---: | ---: | ---: |
| Open-low-high-close | +35 | -115 | -115 |
| Open-high-low-close | +35 | -115 | +85 |

The combined-minus-time difference changes from -150 to +50 bp without changing
the candles. This establishes a possible ordering effect, not its frequency in
NSE stocks or the preferred exit policy. See the [synthetic findings](results/initial_findings.md),
[ledger](results/synthetic_examples.csv) and [paired comparisons](results/synthetic_comparisons.csv).

## Repository guide

| Path | Purpose |
| --- | --- |
| `src/path_robust/engine.py` | Three-policy execution and explicit unresolved outcomes. |
| `src/path_robust/data.py` | Canonical single-instrument OHLC input validation. |
| `src/path_robust/vendor.py` | Streaming parser for the declared instructor CSV schema. |
| `src/path_robust/research.py` | Past-only features, matched episodes, session cash accounts and a descriptive expected-shortfall calculation. |
| `scripts/prepare_pilot.py` | Selected-archive staging, SQLite ingestion and private input audit. |
| `scripts/run_pilot.py` | Session-by-session development replay and separated aggregate/private outputs. |
| `scripts/run_limited.py` | Windows process-tree memory limit and resource report. |
| `tests/` | Deterministic execution, input, chronology and accounting checks. |
| `examples/` | Synthetic inputs only. |
| `results/` | Labelled M3 synthetic outputs and current deterministic checks. |
| `results/m4_pilot/` | Aggregated M4 market development outputs, separately labelled from synthetic results. |
| `config/m4_pilot.json` | Versioned, predeclared development-pilot specification. |
| `METHODS.md` | Implemented rules and interpretation limits. |
| `PIPELINE.md` | Completed components, remaining validation and final evaluation. |
| `CONTRIBUTORS.md` | Group membership, proposed workstreams and access status. |

## Collaboration and access

Repository: https://github.com/I-am-Uchenna/nse-intraday-risk-controls

The course's source-code guideline requests a private repository. This existing
repository remains public, and the visibility decision is deferred. Public
readability does not establish the group members' collaboration permissions or
confirm that instructor access has been checked. Those permissions and the
private-repository requirement remain to be resolved; no compliance claim is
made. See [CONTRIBUTORS.md](CONTRIBUTORS.md).

Do not commit instructor data, derived price databases, course documents, contact
details, credentials, access tokens or private sharing links. Public outputs must
not disclose restricted prices or input records.

## Research context

The distinction between a candle's price range and its unknown ordering is
examined by Stanislaus Maier-Paape and Andreas Platen in
[“Backtest of Trading Systems on Candle Charts,” *IFTA Journal*, 2016, pp. 10–17](https://www.ifta.org/assets/docs/d_ifta_journal_16.pdf).
This repository implements the declared study scenarios, not their entire
algorithm. Related model-based work includes Tim Leung and Xin Li,
[“Optimal Mean Reversion Trading with Transaction Costs and Stop-Loss Exit”](https://arxiv.org/abs/1411.5062v3),
and Alexander Lipton and Marcos Lopez de Prado,
[“A Closed-Form Solution for Optimal Mean-Reverting Trading Strategies”](https://arxiv.org/abs/2003.10502v1).
Those studies do not establish performance for this NSE equity strategy. The
accompanying capstone review provides the broader literature and competitor analysis.
