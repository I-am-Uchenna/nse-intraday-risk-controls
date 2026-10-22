# Module 6 research notebook

**Path-Robust Risk Controls for Intraday Mean Reversion in NSE Equities**  
MScFE 690 | Group 17838  
Uchenna Splendor Ejike, Israel Olanrewaju Odeajo and Goodness Chibueze Kalu

## Run in Colab

[Open the M6 notebook](https://colab.research.google.com/github/I-am-Uchenna/nse-intraday-risk-controls/blob/main/NSE_Intraday_M6.ipynb), or upload `NSE_Intraday_M6.ipynb` to Colab and save a copy in Drive.

1. Use a fresh hosted CPU runtime. No GPU is needed.
2. Make the instructor's stock and index folders available through My Drive shortcuts. Set `CASH_FOLDER` and `INDEX_FOLDER` to their paths.
3. Keep `RUN_STAGE = "validation"` for the M6 continuation. Set `SAVE_FOLDER` to the results folder in Drive.
4. Select **Runtime > Run all**, connect Drive, and wait for the export cell. Check that no cell reports an error.
5. Review source coverage, exclusions, synthetic checks and `ledger_reconciliation.csv` before interpreting the results. Save the executed notebook and the generated output ZIP.

The notebook contains all research functions. It does not clone the repository or execute hidden research scripts. Colab supplies the scientific Python packages; `libarchive-tools` is installed for reading the instructor's archives. Runtime versions are saved with each completed run. For local use, install dependencies with `python -m pip install -r requirements.txt`. This includes `requirements-notebook.txt`; archive ingestion also needs system `bsdtar` or Windows tar.

The archives stay unchanged. Selected series stream into a disk-backed database on the hosted runtime. Strategy replay reads one session at a time. This uses Colab memory and disk, not the computer's Python process. No instructor prices or detailed private trade ledgers are distributed in the repository.

## Scope and evidence

The strategy, five-stock universe, three exit policies and seven execution settings remain fixed. `config/m6_validation_plan.json` records the plan before the new validation outcomes.

| Stage | Dates | Use |
|---|---|---|
| Development | 1 January 2021–17 October 2022 | Existing findings retained in `results/development_20261001` |
| Validation | 18 October 2022–25 May 2023 | M6 continuation: 148 scheduled sessions before exclusions |
| Final reserved | 26 May–29 December 2023 | Strategy evaluation disabled in this interim notebook |

Raw archive preparation includes later dates. This is distinct from evaluating later strategy outcomes. Validation may use earlier prices as past signal history; it cannot evaluate final-period sessions. Protocol freezing is also disabled in this release.

## Completed validation

Run `20261018T084332Z-ghd27dnw` completed the 25 code cells without recorded errors. Their execution counts are 3–27 because the initial Drive mount required retries; this is not described as an untouched fresh-kernel run. The revised notebook has 53 cells (26 code cells): 24 unchanged original code cells, one revised export cell and one new diagnostics cell. The recorded execution predates the 22 October peer-review additions. The trading and inference cells are unchanged; the current notebook adds a post-analysis diagnostics cell and extends the export. Those additions have separate aggregate-only checks and are not represented as a new full market replay. The [execution record](results/m6_verification/execution_check.json) and [source verification](results/m6_verification/source_verification.json) preserve the identities and runtime details.

All 148 validation sessions were evaluable under both timestamp assumptions. The 14 scenario reconciliations passed, with a maximum accounting difference below INR 0.000000001. Source preparation reverified 216 selected symbol-month entries, retained 1,669,406 rows, and excluded 1,883 verified copied rows. These input totals cover the three-year source window; strategy results cover only the validation partition.

| Reference execution, O-L-H-C | Start labels | End labels |
|---|---:|---:|
| Combined minus time, mean daily P&L (bp of fixed capital) | −0.6885 | −0.3855 |
| Combined / time ES97.5 loss (bp) | 11.8599 / 13.3647 | 12.0332 / 13.9353 |
| Combined / time funded minute-close maximum drawdown (%) | 4.0344 / 3.0080 | 3.6181 / 3.0476 |
| Ambiguous / unique episodes | 0 / 266 | 1 / 260 |

Combined exits had lower mean returns and lower descriptive ES, but greater funded drawdown. All three policies had negative mean returns under reference costs. The start-label nominal interval excludes zero, but it remains exploratory because the procedure's coverage is unverified. The ES tail contains only 3.7 days of probability mass. No final-test outcomes were evaluated.

The [validation outputs](results/validation_20261018), [development outputs](results/development_20261001) and [stage comparison](results/m6_comparison_20261018) are kept separately. All 24 validation exports match the original downloaded ZIP byte for byte; [SHA256SUMS.txt](results/validation_20261018/SHA256SUMS.txt) records their checksums. The executed notebook remains outside the repository because its outputs contain private Drive/runtime paths and a worked market-signal observation. The clean notebook, aggregates and execution verification are provided here.

The M6 changes add an independent reconciliation of trade P&L, cash movements, daily totals and matched episodes; a boundary test; and a fuller runtime record. The engine still models assumed fills. Passing software checks does not establish profitable trading, actual fills or reliable statistical coverage.

This reconciliation checks arithmetic within exported account-days. It uses recorded fees and effective exit prices, which already include any added stop slippage. Resolved trades are checked even on incomplete days, but unknown daily totals remain unknown. It does not establish the correctness of fill prices or fee assumptions, recover missing outcomes, or independently verify funded cash continuity and drawdown.

All nominal moving-block intervals remain exploratory because the earlier synthetic diagnostic found undercoverage. Expected shortfall is descriptive and must be reported with its effective tail mass. Session-reset returns and continuously funded drawdowns use different accounting and may use different samples; they must not be pooled.

## Reproduce software checks

From the repository root in PowerShell, run:

```powershell
$env:PYTHONPATH = ".\src"
python -m unittest discover -s tests -v
```

These checks use synthetic inputs and small fixtures. They do not require the instructor's market data. The recorded M6 check run passed 111 tests. Its source hashes and memory measurement are kept with the M6 verification record; the memory measurement applies only to that local check process.

## Compare saved stages

Reproduce the comparison from the saved aggregates into a new output folder:

```bash
python scripts/summarize_m6.py --development results/development_20261001 --validation results/validation_20261018 --output results/m6_comparison_reproduced
```

This standard-library helper checks stage identities, common sample sizes and paired arithmetic. It writes `comparison.csv`, `sensitivity.csv` and `summary.json`. It does not read raw prices, evaluate final outcomes or overwrite an existing summary. Keep stage names and run identifiers attached to every table.

## Peer-review additions (22 October 2026)

The review dated 17 October is addressed through the report response and additional diagnostics, while the topic, entry rule, stock universe, three exits, split dates and final-test guards stay fixed. The new notebook cell displays gross/net fee decomposition, distinct sample counts, full numeric execution sensitivity and all three policies' expected-shortfall leave-one-day-out ranges. It operates on completed run tables and does not re-estimate a strategy or access additional prices.

Reproduce the same tables from saved development and validation aggregates:

```bash
python scripts/peer_review_diagnostics.py --development results/development_20261001 --validation results/validation_20261018 --output results/peer_review_reproduced
```

The [recorded diagnostic tables](results/peer_review_20261022) preserve both stages and source hashes. Gross returns are averages before the assumed fixed fees, not returns above a random-entry baseline. Sensitivity settings remain descriptive; tail deletion ranges are not confidence intervals. New baselines or parameter grids would require a separately documented exploratory study. Validation is already inspected and is not pooled with the untouched final partition.

