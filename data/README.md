# Market-data handling

Market files are supplied separately. Their audit and integration are pending.
No market file, contact information, access token or data-sharing URL is included
in this repository.

Keep raw data immutable and outside version control. Record checksums, coverage,
schema, source permissions and cleaning decisions in the local audit. Do not
upload instructor-supplied or licensed data without permission to redistribute it.

The current single-instrument input schema is:

```text
symbol,timestamp,open,high,low,close
SYNTHETIC,2024-01-02T10:00:00+05:30,100,101.5,98.5,100
```

The row above is synthetic. Timestamps must identify the start of each minute
and include their UTC offset. An adapter must establish those semantics from
the actual source; relabelling end-stamped bars as start-stamped bars would alter
the experiment. `load_bars` checks syntax, chronological order and OHLC bounds.
It does not verify trading sessions, corporate actions, volume or stock/index
alignment. Those checks remain required before market results are computed.
