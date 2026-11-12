# Results index

Each folder holds aggregate outputs from one run. Folders are never overwritten; a new run gets a new dated folder. Raw prices and detailed trade ledgers are excluded.

| Folder | Contents |
| --- | --- |
| [m4_pilot](m4_pilot/) | Frozen Q1 2021 pilot: scenario means, paired contrasts, sensitivity, reconciliation |
| [development_20261001](development_20261001/) | Development stage, 1 Jan 2021 to 17 Oct 2022 |
| [validation_20261018](validation_20261018/) | Validation stage, 18 Oct 2022 to 25 May 2023 |
| [m6_comparison_20261018](m6_comparison_20261018/) | Development versus validation comparison |
| [peer_review_20261022](peer_review_20261022/) | Gross/net returns, sample counts, execution and ES sensitivity |
| [m6_verification](m6_verification/) | M6 execution, source and software checks |
| [m7_validation_20261111](m7_validation_20261111/) | Validation reproduced with the M7 notebook |
| [m7_validation_20261112](m7_validation_20261112/) | Validation rerun with the 23 June 2023 source amendment; its freeze was superseded by a gate fix ([record](../config/m7_source_amendment.md#record-of-review)) |
| [m7_validation_20261112b](m7_validation_20261112b/) | Validation rerun with the corrected notebook; the freeze the final test was checked against |
| [m7_final_20261112](m7_final_20261112/) | The single approved final test, 26 May to 29 December 2023 (88 of 148 sessions evaluable) |

New M7 runs are added from the notebook's publish cell, which names them `m7_<stage>_<YYYYMMDD>` and never overwrites a folder. Column definitions for every table are in the [repository guide](../docs/REPOSITORY_GUIDE.md#result-table-dictionary).

Files directly in this folder are the M3 synthetic examples (`synthetic_*.csv`, `synthetic_summary.json`, `initial_findings.md`) and M4 verification records (`*_verification.json`, `checks.json`).

The written M7 results note, [reports/m7_results/RESULTS.md](../reports/m7_results/RESULTS.md), is built from the peer-review gross table, the development and validation aggregates, and the 11 November 2026 reproduction. It does not add a new market run.
