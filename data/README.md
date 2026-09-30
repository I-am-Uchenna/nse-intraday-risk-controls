# Market-data handling

Instructor market files are supplied separately and are not redistributed in
this repository. Keep original archives immutable. Local staging, normalized
prices, SQLite databases, detailed market ledgers and private account outputs
belong under an excluded work directory such as `data/m4_pilot/`.

The M4 preparation script reads only the archive members named by the frozen
pilot configuration. It records provenance, checksums, coverage diagnostics and
source-label information before replay. This selected-file audit is not a
certification of the entire delivered collection. Do not combine overlapping or
headerless supplements without a documented precedence and schema decision.

## Two input representations

The canonical engine input is:

```text
symbol,timestamp,open,high,low,close
SYNTHETIC,2024-01-02T10:00:00+05:30,100,101.5,98.5,100
```

The example is synthetic. Canonical timestamps identify minute starts and carry
an explicit UTC offset. `load_bars` checks chronology and OHLC validity; it does
not establish exchange sessions or the source's original time semantics.

The vendor adapter reads the supplied header:

```text
<ticker>,<date>,<time>,<open>,<high>,<low>,<close>,<volume>
```

An explicit ninth `<o/i>` or blank header is accepted, with its value treated as
an uninterpreted string by the parser. Dates must be MM/DD/YYYY and times must
be HH:MM:SS. Raw labels remain timezone-naive until the caller explicitly applies
the pilot assumptions. Headerless files, invalid or unordered rows, duplicates
and unexpected symbols are rejected; data are not silently repaired.

## Timing, calendar and availability

The M4 replay evaluates both assumed minute-start and minute-end labels under
an assumed Asia/Kolkata time zone. This does not verify either interpretation.
Use the declared trading calendar, including missing sessions, rather than
inferring the calendar from observed records. Missing windows remain missing;
no forward-filled prices or substituted older histories are created.

The selected nonstandard session is excluded as declared in the configuration
and retained in the history as missing. This is a retrospective data/design
exclusion, so its losses are not estimated and it cannot be described as a
historically available trading safeguard.

Before final evaluation, resolve source timestamp semantics, adjustments,
coverage, session exceptions, historical-universe claims and any permission
limits. Report unresolved assumptions explicitly.

## Sharing

The `.gitignore` excludes local data and general CSV/archive formats, with
specific exceptions for the synthetic examples. Do not treat ignore rules as
a permission check: inspect every proposed public file before committing.
Only appropriately labelled aggregate diagnostics and results belong in public
outputs. Keep raw prices, individual market trade records, private sharing links,
contact details, credentials and tokens out of the repository.
