# Source amendment M7-A1-2023-06-23

**Status:** declared before the protocol freeze and before any final-test outcome was computed.
**Recorded:** 12 November 2026 (to be approved by the group before the freeze).
**Implemented in:** `notebooks/NSE_Intraday_M7.ipynb`, cell `research-011` (`SOURCE_AMENDMENTS`, `supplement_rows`, `fold_preopen`, `apply_source_amendments`); tests in `tests/test_m7_source_amendment.py`.

## Finding
A read-only audit of the June 2023 cash data (row counts and comparisons only; no strategy run) found:

- `Cash Data June 2023.rar` has all 21 June sessions, but on **23 June 2023** it lacks **14:16 to 14:57 (42 minutes)** for all five study stocks.
- Its 14:15 and 14:58 bars on that date are **partial**: their volumes are 4 to 27% of the supplementary values, and some prices differ.
- The instructor supplement `Cash - June 2023- Missing Data.7z` (files dated July 2024) holds the **complete 23 June session** for every stock, in a headerless layout: `YYYYMMDD,HH:MM,open,high,low,close,volume,extra`, with a separate 09:07 pre-open auction row.
- On the 333 to 334 minutes both files share, 97 to 99% of bars are identical. The differences are (a) the pre-open auction, which the monthly files merge into 09:15 and the supplement keeps as its own row; (b) the partial bars at the edges of the gap; and (c) tick-sized revisions.

Without this amendment, the gap makes 23 June unusable and, through the 20-session same-clock look-back, also removes the affected afternoon decision times for about the next 20 sessions of the final partition.

## Rule
For the five study stocks and **23 June 2023 only**:

1. Delete every bar from the monthly file for that date.
2. Insert the supplement session, after merging its single flat pre-open row into the 09:15 bar as the monthly files do: open = pre-open price, high and low over both rows, close = 09:15 close, volumes summed.
3. Record the archive checksum, a fingerprint of the inserted rows, and per-stock counts of removed, inserted, filled, shared and identical minutes in the input audit.

No other date, file or the index is changed.

## Quality gates (the run stops if any fails)
- exactly one supplement archive is found under the data folders;
- every row parses, falls on 23 June, has valid prices and volume, and is strictly increasing in time;
- there is exactly one flat pre-open row and a 09:15 bar;
- every minute from 09:15 to 15:29 is present after the merge;
- at least 95% of shared session minutes are identical, and no shared-minute price differs by more than 50 bp. These limits were set to catch a wrong or corrupted file, not tuned to any result.

The index (`.NSEI`) is not amended. Its coverage on 23 June is reported in the audit so the group can confirm the amendment actually restores the affected sessions.

## Effect on earlier stages
The notebook loads 2021 to 2023 in every run, so the amendment also runs, and is reported, in development and validation runs. Their results cannot change: 23 June 2023 is after the validation period, and signals use past data only. The input-data fingerprint and the protocol record do change, so the validation run that precedes the freeze must be repeated with this notebook version.
