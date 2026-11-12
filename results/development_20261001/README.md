# Expanded M4 development results

This folder preserves aggregate outputs from development run
`20261001T221531Z-th2hk303`, completed on 1 October 2026. Its evaluated window is
1 January 2021 to 17 October 2022: 443 scheduled sessions, with 360 start-label
and 381 end-label complete-case sessions for the primary comparison. Source
preparation covers the declared 2021-2023 six-series window; that audit is not
an evaluation of later strategy outcomes. Validation and the final test remain
unevaluated.

The primary comparison remains combined stop-loss and profit-target exits
against time-only exits for the same intraday mean-reversion entries. The
reference combined-minus-time means are -0.2324787 bp/day for start labels and
-0.1273286 bp/day for end labels. Both nominal intervals include zero. Lower
observed independent-session expected shortfall accompanies lower mean returns;
funded drawdown is higher. There are no observed reference-scenario dual-barrier
episodes on the common evaluable dates. This sample does not measure the effect
of that ambiguity or establish executable profitability.

## Run identity and interpretation

These outputs were executed using
[commit 8b40cf6](https://github.com/I-am-Uchenna/nse-intraday-risk-controls/tree/8b40cf6e4170a157095ecfc28d0579cf1299c99a).
The original [run manifest](run_manifest.json) and protocol identity are retained.
The later [source revision 8d710c9](https://github.com/I-am-Uchenna/nse-intraday-risk-controls/tree/8d710c9e9fb1d6e1bb16dcdbcf08c6306911dddf)
changed interpretation wording and presentation without rerunning the market
study. It has not completed another full hosted run. Publishing this snapshot
is not a new execution.

**All nominal bootstrap intervals are exploratory**, including any that exclude
zero. Synthetic reliability diagnostics show undercoverage for some tested
processes. Confirmatory inference would require a separately documented and
assessed method amendment before final outcomes are opened. A freeze or passing
software checks does not establish statistical reliability.

The source artifacts in this folder are byte-for-byte copies of the saved
outputs. Preserve them as an immutable historical snapshot; put later runs in
separate dated folders. Historical HTML and conclusion files are omitted to
avoid presenting their earlier interpretation as current guidance.

## Files

| Files | Purpose |
| --- | --- |
| `policy_means.csv`, `paired_effects.csv`, `aligned_sensitivity.csv` | Three-policy means and paired development comparisons. |
| `intervals.csv` | Exploratory paired moving-block intervals and support status. |
| `expected_shortfall.csv`, `tail_dates.csv` | Descriptive ES97.5, tail weights and sensitivity. |
| `funded_drawdown.csv` | Funded drawdown at minute/boundary and daily-close frequencies. |
| `exit_ambiguity.csv`, `status_counts.csv` | Observed ambiguity counts and accounting-status counts. |
| `calendar_split.csv`, `coverage_daily.csv`, `coverage_monthly.csv` | Declared chronological partitions and input coverage; later coverage is not later performance. |
| `run_manifest.json`, `input_audit.json` | Original protocol, runtime, source-file hashes and selected-source audit. |
| `bootstrap_reliability.csv`, `bootstrap_reliability_audit.json` | Synthetic coverage/width diagnostics, settings and eligibility masks. |
| `*.png` | Aggregate plots; `synthetic_ambiguity.png` is an artificial illustration, not a market result. |
| `publication_metadata.json` | Source identities, publication boundaries and fresh bounded software-check evidence. |
| `SHA256SUMS.txt` | SHA-256 checksums for every other file in this snapshot. |

The fresh check ran 104 existing repository tests without failures, errors or
skips. It used a 384 MiB aggregate committed-memory cap, with a measured peak of
29.03 MiB. These were software and synthetic checks, not market evaluation.
Details and the tested source identity are in `publication_metadata.json`.

## Reproduction and data boundaries

Use the [research notebook](../../NSE_Intraday_Research.ipynb) and
[repository instructions](../../README.md) with the original instructor inputs
to reproduce the study. Use the executed commit above to reproduce this
historical source version. The original run records Python 3.13.15, NumPy 2.1.3
and pandas 2.2.3. Its exact Matplotlib version was not recorded.

This folder contains no instructor OHLC price rows, source archives, private
price databases, detailed trade/cash ledgers, credentials or private sharing
links. Source filenames, checksums, coverage counts, aggregate statistics and
portfolio tail dates are retained for audit. The original Q1 pilot remains in
[results/m4_pilot](../m4_pilot/); its twenty-session findings are a separate record.
