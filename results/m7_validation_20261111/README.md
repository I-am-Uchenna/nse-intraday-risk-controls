# M7 validation reproduction — 11 November 2026

**Path-Robust Risk Controls for Intraday Mean Reversion in NSE Equities**

Uchenna Splendor Ejike, Israel Olanrewaju Odeajo and Goodness Chibueze Kalu · Group 17838

We completed run `20261111T081528Z-fzxevfhy` in Google Colab on 11 November 2026 at 08:22:50 UTC using the instructor's original archives. All 27 code cells executed, with no saved errors. The executed notebook's normalized code identity matches the reviewed M7 source.

We compared 17 aggregate tables with the recorded validation results in [`validation_20261018`](../validation_20261018/) and the validation rows in [`peer_review_20261022`](../peer_review_20261022/). Every compared numeric value matched exactly; the comparison tolerance was 1e-9 with zero relative tolerance. All fourteen ledger reconciliations and twenty-four identity, stage and consistency checks passed. [`verification.json`](verification.json) records the checks and table counts.

This reproduces the previously observed validation period, 18 October 2022–25 May 2023; it is not a new test sample. `final_test_evaluated` is **false**, and no final-access record is included. The trading settings, calendar, source-data fingerprint and inference settings match the historical validation. M7 adds protocol controls and clearer result reporting.

Read [`gross_net_returns.csv`](gross_net_returns.csv) first for gross returns, assumed fees and net returns, followed by the exit comparisons and risk tables. [`run_manifest.json`](run_manifest.json) records the run identity, settings and runtime; [`input_audit.json`](input_audit.json) records source counts and checksums. The coverage files describe source availability across the delivered archives, not final-test strategy outcomes. Raw prices, private ledgers and the executed notebook are excluded from this public export.

The run used Python 3.13.18, NumPy 2.4.6, pandas 2.2.3 and Matplotlib 3.10.0. [`runtime-requirements.txt`](runtime-requirements.txt) records the exact installed Python-package versions from the manifest. It is a run-specific environment record; the repository's general requirements are unchanged. Historical validation used Python 3.13.16 and NumPy 2.1.3; these version changes produced no difference in the compared values.

The original outputs ZIP had SHA-256 `96092378eb9cb5d0b7ac680c004c6aa2ba4a12bd9bdaf2b191033c4300d7c0ef`. Its 28 members are preserved byte-for-byte here. [`SHA256SUMS.txt`](SHA256SUMS.txt) covers those exports and the supporting files in this folder.
