# Source amendment M7-A1-2023-06-23 and known final-period coverage

**Status:** declared before the protocol freeze and before any final-test outcome was computed.
**Recorded:** 12 November 2026; revised on 12 November 2026 after the pre-final review, before the second validation freeze (see "Record of review" below).
**Implemented in:** `notebooks/NSE_Intraday_M7.ipynb`, cell `research-011` (`SOURCE_AMENDMENTS`, `supplement_rows`, `fold_preopen`, `apply_source_amendments`); tests in `tests/test_m7_source_amendment.py`.

## Finding
A read-only audit of the June 2023 cash data (row counts and comparisons only; no strategy run) found:

- `Cash Data June 2023.rar` has all 21 June sessions, but on **23 June 2023** it lacks **14:16 to 14:57 (42 minutes)** for all five study stocks.
- Its 14:15 and 14:58 bars on that date are **partial**: their volumes are 4 to 27% of the supplementary values, and some prices differ.
- The instructor supplement `Cash - June 2023- Missing Data.7z` (files dated July 2024) holds the **complete 23 June session** for every stock, in a headerless layout: `YYYYMMDD,HH:MM,open,high,low,close,volume,extra`, with a separate 09:07 pre-open auction row.
- On the 333 session minutes both files share, 322 to 328 bars per stock (96.7 to 98.5%) are identical. The differences are (a) the pre-open auction, which the monthly files merge into 09:15 and the supplement keeps as its own row; (b) the partial bars at the edges of the gap; and (c) tick-sized revisions.

## Rule
For the five study stocks and **23 June 2023 only**:

1. Delete every bar from the monthly file for that date.
2. Insert the supplement session, after merging its single flat pre-open row into the 09:15 bar as 35 of the 36 monthly stock files do: open = pre-open price, high and low over both rows, close = 09:15 close, volumes summed. The 09:15 open, high and low are never used by a signal or a trade (the earliest window label is 09:29 and the earliest entry 09:46), so this choice cannot affect results.
3. Record the archive checksum, a fingerprint of the inserted rows, and per-stock counts of removed, inserted, filled, shared and identical minutes in the input audit.

No other date, file or the index is changed. Rows after 15:29 are inserted as delivered and are ignored by the session reader, as in every monthly file.

## Quality gates (the run stops if any fails)
- exactly one supplement archive is found under the data folders;
- every row parses, falls on 23 June, has valid prices and volume, and is strictly increasing in time;
- there is exactly one flat pre-open row and a 09:15 bar;
- every minute from 09:15 to 15:29 is present after the merge;
- at least 95% of shared session minutes are identical, and no shared-minute price differs by more than 50 bp. These limits were set to catch a wrong or corrupted file, not tuned to any result.

The 12 November validation run passed every gate: 42 minutes filled per stock, 322 to 328 of 333 shared minutes identical, largest shared-minute price gap 6.7 to 10.5 bp.

## Index gap on the same date
The validation run of 12 November 2026 reported 42 index session minutes missing on 23 June 2023. A direct check of the raw file `NSE Indices-June 2023/.NSEI.csv` confirmed the gap: the labels jump from 14:15 to 14:58, leaving 333 of 375 session minutes, the same 14:16 to 14:57 window as the stocks. No index supplement was supplied, so the index is not amended.

The 14:45 decision on that date therefore has no index return, under both timestamp readings; the 14:15 decision is unaffected. Under the unchanged complete-day rule, 23 June and the 20 following sessions, whose 20-session history for the 14:45 slot includes it, are classed as incomplete and leave the primary comparison.

The amendment therefore does not change which sessions are evaluable. What it does change is the funded accounts: a 14:15 signal on 23 June enters at 14:16, a minute missing from the original stock file. Without the amendment such a trade would meet unknown prices, its accounts would become unknown equity, and with no restart dates declared they would stop for the rest of the final period. With the amendment the trade is valued from delivered prices.

Under the end-label reading only, the 14:15 decision on 23 June uses the close of the index's raw 14:15 bar, which, like the stocks' 14:15 bar in the monthly file, is presumably partial. This cannot affect the primary sample, which already excludes that date and the next 20 sessions; it can affect funded 14:15 signals on that date and 14:15-slot z-scores in the next 20 sessions under the end label.

## Other known coverage gaps in the final period
The public coverage table (`coverage_daily.csv`, minute counts only; no prices, returns or signals) shows four more final-period dates with missing minutes. None has a supplement, and none is amended.

| Date | Missing | Expected effect under the unchanged rules |
|---|---|---|
| 20 July 2023 | RELIANCE has 331 of 375 session minutes; 09:15 is among the missing minutes, consistent with that day's special pre-open session for the Jio Financial Services demerger | The 09:45 decision for RELIANCE has no stock return, so the date and the next 20 sessions are incomplete |
| 22 September 2023 | No stock bars at all (the September file holds a copy of 22 August instead, which is detected and excluded) | The date and the next 20 sessions are incomplete |
| 12 September 2023 | 2 minutes for every stock | Incomplete only if a missing minute falls in a signal window; a missing minute inside a holding window makes that day's funded accounts unknown equity |
| 26 October 2023 | 3 minutes for every stock | As for 12 September |

Counting from the calendar, 23 June, 20 July and 22 September together leave 88 of the 148 final sessions evaluable, in three runs (26 May to 22 June, 21 August to 21 September, 25 October to 29 December). If the gaps on 12 September and 26 October also fall in signal windows, 60 remain. The 23 June index gap alone accounts for 18 of the excluded sessions, because 20 July's exclusion overlaps the rest. Validation had no incomplete days.

These are expectations from metadata. The final run's sample accounting reports the actual numbers, and short runs of evaluable days may leave some bootstrap intervals unavailable under the declared minimum-support rule. No rule, date, threshold or restart is changed in response.

## Effect on earlier stages
The notebook loads 2021 to 2023 in every run, so the amendment also runs, and is reported, in development and validation runs; coverage metadata for the final period is therefore visible before final access, as it has been since M6. Development and validation results cannot change: 23 June 2023 is after the validation period, the replay reads no session after the last evaluation date, and signals use past data only. The input-data fingerprint and the protocol record do change, so the validation run that precedes the freeze must be repeated with this notebook version.

## Record of review
- The first validation run with this amendment (`20261112T145910Z-mcheh48a`, published as `results/m7_validation_20261112`) reproduced every validation table and was frozen.
- A three-reviewer check before final access then found that the freeze could never be matched: `SOURCE_AMENDMENTS` was a Python tuple, which becomes a list when the freeze is saved as JSON, so the final-access comparison would always refuse. It would have refused before writing an access record or reading any final-period outcome.
- The fix changes `SOURCE_AMENDMENTS` to a list and adds a test that saves and reloads the real payload. No research rule, setting, date or threshold changed. Because the code fingerprint is part of the protocol record, the earlier freeze is superseded: it is kept, renamed, as `m7_protocol_freeze_superseded_20261112.json` in the save folder and as published in `results/m7_validation_20261112`, and validation is repeated and frozen again with the corrected notebook.
- The same review found the four further final-period gaps above, which are declared here before the new freeze.
