"""Streaming parser for the declared instructor CSV layout.

The raw timestamp is a naive source label. Neither the CSV header nor successful
parsing verifies its timezone or whether it labels a minute's start or end.
``as_bar`` makes those pilot assumptions explicit. Headerless supplements are
rejected: their provenance and conflicts require a separate reconciliation rule.
No row is dropped, forward-filled, deduplicated or sorted by this adapter.
"""

import csv
import re
from dataclasses import dataclass
from datetime import datetime
from math import isfinite
from typing import Iterable, Iterator

from .engine import Bar, IST, MINUTE


_FIELDS = ("<ticker>", "<date>", "<time>", "<open>", "<high>", "<low>", "<close>", "<volume>")
_DATE = re.compile(r"[0-9]{2}/[0-9]{2}/[0-9]{4}")
_TIME = re.compile(r"[0-9]{2}:[0-9]{2}:[0-9]{2}")


@dataclass(frozen=True)
class VendorRow:
    symbol: str
    raw_timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    extra: str | None = None

    def __post_init__(self) -> None:
        if not self.symbol or self.symbol.strip() != self.symbol:
            raise ValueError("symbol must be nonempty and have no surrounding spaces")
        if not isinstance(self.raw_timestamp, datetime) or self.raw_timestamp.tzinfo is not None:
            raise ValueError("raw_timestamp must be a naive source label, with timezone unverified")
        if self.raw_timestamp.second or self.raw_timestamp.microsecond:
            raise ValueError("source labels must be at minute boundaries")
        prices = (self.open, self.high, self.low, self.close)
        if any(not isfinite(value) or value <= 0 for value in prices):
            raise ValueError("OHLC prices must be finite and positive")
        if not self.low <= min(self.open, self.close) <= max(self.open, self.close) <= self.high:
            raise ValueError("OHLC must satisfy low <= open, close <= high")
        if not isfinite(self.volume) or self.volume < 0:
            raise ValueError("volume must be finite and nonnegative")
        if self.extra is not None and not isinstance(self.extra, str):
            raise ValueError("the optional ninth field must remain an uninterpreted string")

    def as_bar(self, label: str = "start") -> Bar:
        """Assume IST; map an assumed start/end label to a minute-start Bar.

        End-labelled observations shift back one minute, including across midnight.
        Session filtering belongs after this conversion. The raw label is retained
        unchanged on this VendorRow for provenance and timing-sensitivity checks.
        """
        if label not in ("start", "end"):
            raise ValueError("label must be 'start' or 'end'; source semantics remain an assumption")
        timestamp = self.raw_timestamp.replace(tzinfo=IST)
        if label == "end":
            timestamp -= MINUTE
        return Bar(self.symbol, timestamp, self.open, self.high, self.low, self.close)


def iter_vendor_rows(lines: Iterable[str], symbol: str) -> Iterator[VendorRow]:
    """Yield one validated row at a time; require an explicit eight/nine-field header.

    Dates must be MM/DD/YYYY and times HH:MM:SS at minute boundaries. An explicit
    eight-field header has no extra field; a nine-field header ends in ``<o/i>``
    or a blank name. Its value is retained without interpreting it as open interest.
    Missing minute labels are preserved as gaps rather than generated observations.
    Validation of later rows is naturally deferred until the iterator reaches them.
    """
    if not symbol or symbol.strip() != symbol:
        raise ValueError("expected symbol must be nonempty and have no surrounding spaces")
    reader = csv.reader(lines, strict=True)
    try:
        first = next(reader, None)
        if first is None:
            raise ValueError("CSV is empty; an explicit supported header is required")
        header = tuple(value.strip() for value in first)
        if header:
            header = (header[0].lstrip("\ufeff"), *header[1:])
        if not (header == _FIELDS or (len(header) == 9 and header[:8] == _FIELDS
                                     and header[8] in ("<o/i>", ""))):
            raise ValueError("unsupported CSV header; headerless supplements and unknown schemas are rejected")
        width = len(header)
        previous = None
        for fields in reader:
            try:
                if len(fields) != width:
                    raise ValueError(f"expected exactly {width} columns, found {len(fields)}")
                actual_symbol, day, clock = (value.strip() for value in fields[:3])
                if actual_symbol != symbol:
                    raise ValueError(f"symbol mismatch: expected {symbol!r}, found {actual_symbol!r}")
                if not _DATE.fullmatch(day) or not _TIME.fullmatch(clock):
                    raise ValueError("date/time must use exact MM/DD/YYYY and HH:MM:SS formats")
                timestamp = datetime.strptime(f"{day} {clock}", "%m/%d/%Y %H:%M:%S")
                value = VendorRow(symbol, timestamp, *(float(field) for field in fields[3:8]),
                                  fields[8] if width == 9 else None)
                if previous is not None and timestamp <= previous:
                    raise ValueError("raw timestamps must be strictly increasing without duplicates")
            except (ValueError, TypeError, OverflowError) as error:
                raise ValueError(f"invalid vendor CSV at line {reader.line_num}: {error}") from error
            previous = timestamp
            yield value
    except csv.Error as error:
        raise ValueError(f"invalid CSV syntax at line {reader.line_num}: {error}") from error
