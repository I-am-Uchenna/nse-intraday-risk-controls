# M7 final-project notebook

**Path-Robust Risk Controls for Intraday Mean Reversion in NSE Equities**  
Uchenna Splendor Ejike, Israel Olanrewaju Odeajo and Goodness Chibueze Kalu · Group 17838

Use `notebooks/NSE_Intraday_M7.ipynb`. It contains the complete experiment, comments, checks, plots and results export. The M6 notebook and its recorded results remain unchanged.

## Run in Google Colab

1. [Open the M7 notebook in Google Colab](https://colab.research.google.com/github/I-am-Uchenna/nse-intraday-risk-controls/blob/main/notebooks/NSE_Intraday_M7.ipynb) and save a copy in Drive. Select a hosted CPU runtime.
2. Add readable My Drive shortcuts to the instructor's **NSE Cash Stocks Data** and **NSE Index Data** folders. Set `CASH_FOLDER`, `INDEX_FOLDER` and `SAVE_FOLDER` in the first code cell. Use the same `SAVE_FOLDER` for validation, its freeze and final evaluation.
3. Keep `RUN_STAGE="validation"` and `FINAL_ACCESS_APPROVED=False`. Select **Runtime → Run all**. Review all cell outputs, source exclusions, fourteen ledger checks and validation results. Save the executed notebook and exported ZIP.
4. Check the printed source amendment summary (five stocks, minutes filled, index minutes missing on that date). Compare the reproduced validation with `results/validation_20261018` and the aggregate diagnostics with `results/peer_review_20261022`. Investigate any numerical difference before proceeding; do not select a better result.
5. After reviewing the completed validation, download its executed notebook and check its normalized code bundle against the reviewed source. Then set `READY_TO_FREEZE=True` in the final save cell and run **only that cell**. It records `m7_protocol_freeze.json` after checking that runtime scientific functions, parsed source data, settings and reconciliations still agree with the executed validation.
6. Final access requires a separate group decision. After approval, reset `READY_TO_FREEZE=False`, start a fresh runtime, select `RUN_STAGE="final"` and `FINAL_ACCESS_APPROVED=True`, then run all cells once. A missing or mismatched freeze blocks replay. An exclusive `m7_final_access.json` is written before final strategy evaluation; an existing access record blocks a second automatic run.
7. Save the executed final notebook and results ZIP. A failed final attempt is still an access event: preserve its record, document the failure and review recovery before another run. Never delete the record to obtain a clean-looking first attempt. Recovery rule, declared before the final run: if a final attempt stops with an error before any final-period result table or figure has been displayed, the group may rename its record to `m7_final_access_attempt1.json`, keep the executed notebook and error, and run once more with unchanged code, data and settings; the report discloses both attempts. If any final-period result was displayed, that attempt's outputs are the final result and no rerun is made.
8. Every run stays in `SAVE_FOLDER` until the group is satisfied with it. Then tick `PUBLISH_RUN` in the publish cell (section 13a), put the run's ID in `PUBLISH_RUN_ID` and rerun only that cell. It refuses incomplete runs, price or trade-level files and inconsistent stage flags, and never overwrites a folder. Locally it writes `results/m7_<stage>_<YYYYMMDD>/`; in Colab it prepares that folder and a ZIP in `SAVE_FOLDER/ready_to_publish/` to unzip into `results/`.

## Run locally (VS Code or Jupyter)

Copy the two instructor folders into the repository `data/` folder and install `bsdtar` (`sudo apt install -y libarchive-tools` on Ubuntu or WSL; Windows `tar` also works). Open the notebook and run all cells, keeping the default folder paths. Outside Colab the first cell switches to `data/`, saves runs to `data/m7_runs/` (not tracked) and shows a setup checklist. The source check before loading shows which file each month will use. No unzipping is needed, because yearly 7z, monthly RAR and extracted CSV layouts are all read directly; keep only one layout per month.

## Source amendment for 23 June 2023

The June 2023 cash file is missing 14:16 to 14:57 on 23 June 2023 for all five stocks, and its 14:15 and 14:58 bars are partial. Declared amendment `M7-A1-2023-06-23` replaces those five stocks' bars for that one date with the instructor's complete supplement (`Cash - June 2023- Missing Data.7z`), merging its pre-open auction row into 09:15 as the monthly files do. The notebook prints a per-stock summary and stops if the supplement fails any quality gate. The record, quality gates and audit findings are in [config/m7_source_amendment.md](../config/m7_source_amendment.md). Because the notebook loads 2021 to 2023 in every run, the amendment also appears in the validation run's input audit. Validation results are unchanged, but its data fingerprint changes, so repeat the validation run with this version before freezing.

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

Start with `gross_net_returns.csv`: it separates gross returns, assumed fees and net returns in daily reference-capital units and per-trade units. Then read `paired_effects.csv`, `expected_shortfall.csv`, `funded_drawdown.csv` and `exit_ambiguity.csv`. The generated conclusions lead with the observed economics and collect the main limitations afterwards. The written note for the report is [reports/m7_results/RESULTS.md](../reports/m7_results/RESULTS.md): the cost finding is the first paragraph, and the qualifications sit together under Limitations.

The exported manifest identifies the stage, runtime versions, input audit, code and protocol. A final export also includes its validation freeze and access record. Shared exports exclude raw prices and private trade/cash ledgers. Review saved notebook outputs for private paths or worked source observations before sharing them.

## Local reproduction and checks

Colab is the primary workflow. For local use, install Python dependencies from the repository root:

```text
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
```

Local archive ingestion also needs `bsdtar` (libarchive-tools), or Windows `tar`. Outside Colab the notebook uses the repository `data/` folder automatically; otherwise set the three folder paths. The downloaded outer ZIPs must first be extracted into their original folder layout; source discovery accepts monthly RAR files, yearly index 7z files, or the corresponding extracted CSVs. Keep only one copy/layout of each selected source under the chosen roots.

The focused M7 checks use synthetic records and existing aggregate tables. They do not access final market outcomes. The declaration `M7_CODE_BUNDLE_SHA256` covers the delivered code cells except folder paths, stage/approval controls, the publish controls and the digest itself; local tests recompute it. Runtime scientific-function and parsed-data hashes are checked again when freezing and before final access. The runtime does not re-read the complete notebook file: the downloaded executed notebook's normalized code bundle must also be checked against the reviewed source before freezing. The freeze is an internal version record, not a guarantee of statistical validity.

## Execution status

On 12 November 2026 validation was rerun locally with the 23 June 2023 source amendment (`results/m7_validation_20261112`). Every validation table matched the 11 November run except the 23 June coverage counts, and the run was frozen. A pre-final review then found that the freeze comparison could never succeed, because the amendment was stored as a tuple; the fix and the four further final-period coverage gaps found in the same review are recorded in [config/m7_source_amendment.md](../config/m7_source_amendment.md). Validation is repeated and frozen again with the corrected notebook before final access.

We completed a fresh M7 validation run on 11 November 2026. All 27 code cells executed without saved errors, all fourteen ledger reconciliations passed, and seventeen aggregate tables matched the historical validation exactly. The executed notebook's normalized code identity matched the reviewed source. The [verified validation export](../results/m7_validation_20261111/) includes the run manifest, comparison record, tables, figures and exact runtime versions.

This run reproduced the previously observed validation period; it did not evaluate the final partition. Final access remains disabled by default, and this export records `final_test_evaluated=false`. Final evaluation requires its separate approval, matching protocol freeze and saved execution evidence.
