"""Explicit CSV input schema for one instrument's minute bars."""

import csv
from datetime import datetime
from pathlib import Path

from .engine import Bar, validate_bars

FIELDS = ("symbol", "timestamp", "open", "high", "low", "close")


def load_bars(path: str | Path, symbol: str) -> list[Bar]:
    with open(path, newline="", encoding="utf-8-sig") as source:
        reader = csv.DictReader(source)
        if reader.fieldnames is None or not set(FIELDS).issubset(reader.fieldnames):
            raise ValueError(f"required CSV fields: {', '.join(FIELDS)}")
        bars = []
        for line, row in enumerate(reader, start=2):
            try:
                bars.append(Bar(row["symbol"], datetime.fromisoformat(row["timestamp"]),
                                *(float(row[key]) for key in FIELDS[2:])))
            except (ValueError, TypeError, KeyError) as error:
                raise ValueError(f"invalid bar at CSV line {line}: {error}") from error
    return validate_bars(bars, symbol)
