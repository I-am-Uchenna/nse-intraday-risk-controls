# M7 final-project notebook

**Path-Robust Risk Controls for Intraday Mean Reversion in NSE Equities**  
Uchenna Splendor Ejike, Israel Olanrewaju Odeajo and Goodness Chibueze Kalu · Group 17838

Use `NSE_Intraday_M7.ipynb`. It contains the complete experiment, comments, checks, plots and results export. The M6 notebook and its recorded results remain unchanged.

## Run in Google Colab

1. [Open the M7 notebook in Google Colab](https://colab.research.google.com/github/I-am-Uchenna/nse-intraday-risk-controls/blob/main/NSE_Intraday_M7.ipynb) and save a copy in Drive. Select a hosted CPU runtime.
2. Add readable My Drive shortcuts to the instructor's **NSE Cash Stocks Data** and **NSE Index Data** folders. Set `CASH_FOLDER`, `INDEX_FOLDER` and `SAVE_FOLDER` in the first code cell. Use the same `SAVE_FOLDER` for validation, its freeze and final evaluation.
3. Keep `RUN_STAGE="validation"` and `FINAL_ACCESS_APPROVED=False`. Select **Runtime → Run all**. Review all cell outputs, source exclusions, fourteen ledger checks and validation results. Save the executed notebook and exported ZIP.
4. Compare the reproduced validation with `results/validation_20261018` and the aggregate diagnostics with `results/peer_review_20261022`. Investigate any numerical difference before proceeding; do not select a better result.
5. After reviewing the completed validation, download its executed notebook and check its normalized code bundle against the reviewed source. Then set `READY_TO_FREEZE=True` in the final save cell and run **only that cell**. It records `m7_protocol_freeze.json` after checking that runtime scientific functions, parsed source data, settings and reconciliations still agree with the executed validation.
6. Final access requires a separate group decision. After approval, reset `READY_TO_FREEZE=False`, start a fresh runtime, select `RUN_STAGE="final"` and `FINAL_ACCESS_APPROVED=True`, then run all cells once. A missing or mismatched freeze blocks replay. An exclusive `m7_final_access.json` is written before final strategy evaluation; an existing access record blocks a second automatic run.
7. Save the executed final notebook and results ZIP. A failed final attempt is still an access event: preserve its record, document the failure and review recovery before another run. Never delete the record to obtain a clean-looking first attempt.

The notebook streams selected source rows into a disk-backed SQLite database and reads one session at a time. Drive storage does not eliminate runtime memory use, but the complete price dataset is not loaded into a pandas DataFrame. Each run creates its own working directory and output folder. Original archives are not altered.

## Fixed experiment

The five stocks are RELIANCE, HDFCBANK, INFY, TCS and ITC, with `.NSEI` as the index. The signal, 20-session history, threshold, barriers, holding period, position sizing, three exits, seven execution settings and both timestamp/path interpretations remain unchanged. The primary comparison is combined minus time-only mean daily P&L divided by fixed reference capital on common evaluable dates. All nominal bootstrap intervals remain exploratory.

| Stage | Dates | Purpose |
|---|---|---|
| Development | 1 Jan. 2021–17 Oct. 2022 | Preserved original development record |
| Validation | 18 Oct. 2022–25 May 2023 | Reproduce and review before freezing |
| Final | 26 May–29 Dec. 2023 | Evaluate once after explicit approval and matching freeze |

The partitions are never pooled. Preparing or fingerprinting source files is separate from evaluating final strategy outcomes. Metadata such as missing source dates can be audited before final replay.

## Reading results

Start with `gross_net_returns.csv`: it separates gross returns, assumed fees and net returns in daily reference-capital units and per-trade units. Then read `paired_effects.csv`, `expected_shortfall.csv`, `funded_drawdown.csv` and `exit_ambiguity.csv`. The generated conclusions lead with the observed economics and collect the main limitations afterwards.

The exported manifest identifies the stage, runtime versions, input audit, code and protocol. A final export also includes its validation freeze and access record. Shared exports exclude raw prices and private trade/cash ledgers. Review saved notebook outputs for private paths or worked source observations before sharing them.

## Local reproduction and checks

Colab is the primary workflow. For local use, install Python dependencies from the repository root:

```text
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
```

Local archive ingestion also needs `bsdtar` (libarchive-tools), or Windows `tar`. Set `CONNECT_DRIVE=False` and the three folder paths before running the notebook locally. The downloaded outer ZIPs must first be extracted into their original folder layout; source discovery accepts monthly RAR files, yearly index 7z files, or the corresponding extracted CSVs. Keep only one copy/layout of each selected source under the chosen roots.

The focused M7 checks use synthetic records and existing aggregate tables. They do not access final market outcomes. The declaration `M7_CODE_BUNDLE_SHA256` covers the delivered code cells except folder paths, stage/approval controls and the digest itself; local tests recompute it. Runtime scientific-function and parsed-data hashes are checked again when freezing and before final access. The runtime does not re-read the complete notebook file: the downloaded executed notebook's normalized code bundle must also be checked against the reviewed source before freezing. The freeze is an internal version record, not a guarantee of statistical validity.

## Execution status

This M7 source starts with final access disabled. Its fresh validation and final executions must have their own saved notebooks, manifests and reconciliation records. The historical M6 execution and its software checks do not establish a completed M7 market run. Do not label the final results complete until that evidence exists.
