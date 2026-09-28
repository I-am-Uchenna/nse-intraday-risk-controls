"""Long-only minute-bar execution assumptions; not a market-fill model.

Bars identify minute starts. A caller supplies an entry episode using only past
information. Barriers are fixed multiples of the observed entry open. No signal
generation, market-data inference or portfolio capital allocation happens here.
"""

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from math import isfinite
from typing import Iterable

MINUTE = timedelta(minutes=1)
IST = timezone(timedelta(hours=5, minutes=30))


class Policy(str, Enum):
    TIME = "time_only"
    STOP = "stop_only"
    COMBINED = "stop_and_target"


class Path(str, Enum):
    LOW_FIRST = "O-L-H-C"
    HIGH_FIRST = "O-H-L-C"


def _minute_time(value: datetime, name: str) -> None:
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise ValueError(f"{name} must be a timezone-aware datetime")
    if value.second != 0 or value.microsecond != 0:
        raise ValueError(f"{name} must identify a minute boundary")


def _positive(value: float, name: str) -> None:
    if not isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be finite and positive")


@dataclass(frozen=True)
class Bar:
    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float

    def __post_init__(self) -> None:
        if not self.symbol or self.symbol.strip() != self.symbol:
            raise ValueError("symbol must be nonempty and have no surrounding spaces")
        _minute_time(self.timestamp, "bar timestamp")
        for key in ("open", "high", "low", "close"):
            _positive(getattr(self, key), key)
        if not (self.low <= min(self.open, self.close)
                <= max(self.open, self.close) <= self.high):
            raise ValueError("OHLC must satisfy low <= open, close <= high")


@dataclass(frozen=True)
class Episode:
    episode_id: str
    symbol: str
    signal_at: datetime
    entry_at: datetime
    expiry_at: datetime
    stop_multiplier: float
    target_multiplier: float
    entry_notional: float = 10_000.0

    def __post_init__(self) -> None:
        if not self.episode_id or not self.symbol:
            raise ValueError("episode_id and symbol are required")
        for key in ("signal_at", "entry_at", "expiry_at"):
            _minute_time(getattr(self, key), key)
        if self.entry_at - self.signal_at < MINUTE:
            raise ValueError("entry must be at least one minute after signal completion")
        if self.expiry_at <= self.entry_at:
            raise ValueError("expiry must be after entry")
        dates = {getattr(self, key).astimezone(IST).date()
                 for key in ("signal_at", "entry_at", "expiry_at")}
        if len(dates) != 1:
            raise ValueError("signal, entry and expiry must share an Indian calendar date")
        if not isfinite(self.stop_multiplier) or not 0 < self.stop_multiplier < 1:
            raise ValueError("stop_multiplier must lie strictly between zero and one")
        if not isfinite(self.target_multiplier) or self.target_multiplier <= 1:
            raise ValueError("target_multiplier must exceed one")
        _positive(self.entry_notional, "entry_notional")


@dataclass(frozen=True)
class Execution:
    round_trip_cost_bp: float = 15.0
    extra_stop_slippage_bp: float = 0.0

    def __post_init__(self) -> None:
        for key in ("round_trip_cost_bp", "extra_stop_slippage_bp"):
            value = getattr(self, key)
            if not isfinite(value) or value < 0:
                raise ValueError(f"{key} must be finite and nonnegative")


@dataclass(frozen=True)
class Result:
    """Episode ledger entry under one declared execution configuration.

    For ``exit_phase == 'within_bar'``, ``exit_at`` is the containing bar's
    start label, not an observed execution timestamp. Exact within-minute exit
    time and holding duration are not identified by the OHLC data.
    """

    episode_id: str
    symbol: str
    policy: str
    path: str
    status: str
    signal_at: datetime
    entry_at: datetime
    expiry_at: datetime
    entry_notional: float
    entry_price: float | None
    stop_price: float | None
    target_price: float | None
    declared_round_trip_cost_bp: float
    declared_extra_stop_slippage_bp: float
    exit_at: datetime | None = None
    exit_reason: str | None = None
    exit_phase: str | None = None
    exit_price_before_slippage: float | None = None
    exit_price: float | None = None
    gross_return_bp: float | None = None
    entry_cost_bp: float | None = None
    exit_cost_bp: float | None = None
    stop_slippage_bp: float | None = None
    net_return_bp: float | None = None
    net_pnl: float | None = None
    exit_order_ambiguous: bool = False
    unresolved_at: datetime | None = None
    issue: str | None = None

    def to_record(self) -> dict:
        return {key: value.isoformat() if isinstance(value, datetime) else value
                for key, value in asdict(self).items()}


def validate_bars(bars: Iterable[Bar], symbol: str) -> list[Bar]:
    """Reject wrong instruments, duplicates and nonchronological records.

    Gaps are retained. The simulator determines whether a gap prevents resolution
    of a particular position; it never repairs a gap with an invented bar.
    """
    output = list(bars)
    previous = None
    for bar in output:
        if bar.symbol != symbol:
            raise ValueError("supply bars for exactly the episode's symbol")
        if previous is not None and bar.timestamp <= previous:
            raise ValueError("bars must be strictly chronological without duplicates")
        previous = bar.timestamp
    return output


def _within_bar(bar: Bar, stop: float | None, target: float | None,
                path: Path) -> tuple[str, float] | None:
    points = ((bar.open, bar.low, bar.high, bar.close) if path == Path.LOW_FIRST
              else (bar.open, bar.high, bar.low, bar.close))
    for start, end in zip(points, points[1:]):
        if start == end:
            continue
        crossed = []
        for reason, level in (("STOP", stop), ("TARGET", target)):
            if level is not None and min(start, end) <= level <= max(start, end):
                distance = (level - start) / (end - start)
                crossed.append((distance, reason, level))
        if crossed:
            _, reason, price = min(crossed)
            return reason, price
    return None


def simulate(bars: Iterable[Bar], episode: Episode, policy: Policy,
             path: Path, execution: Execution = Execution()) -> Result:
    """Resolve one position or return UNRESOLVED with no imputed return.

    Opening gaps precede intrabar paths; expiry at the open precedes both. The
    entire entry candle is eligible because the entry is at its open. Minute
    extrema before entry or after expiry cannot trigger a trade exit.
    """
    policy, path = Policy(policy), Path(path)
    lookup = {bar.timestamp: bar for bar in validate_bars(bars, episode.symbol)}
    first = lookup.get(episode.entry_at)
    price = first.open if first else None
    stop = price * episode.stop_multiplier if price is not None else None
    target = price * episode.target_multiplier if price is not None else None
    base = dict(episode_id=episode.episode_id, symbol=episode.symbol,
                policy=policy.value, path=path.value, signal_at=episode.signal_at,
                entry_at=episode.entry_at, expiry_at=episode.expiry_at,
                entry_notional=episode.entry_notional, entry_price=price,
                stop_price=stop, target_price=target,
                declared_round_trip_cost_bp=execution.round_trip_cost_bp,
                declared_extra_stop_slippage_bp=execution.extra_stop_slippage_bp)

    def unresolved(at: datetime) -> Result:
        return Result(**base, status="UNRESOLVED", unresolved_at=at,
                      entry_cost_bp=execution.round_trip_cost_bp / 2 if first else None,
                      issue="MISSING_ENTRY_BAR" if first is None else "MISSING_REQUIRED_BAR")

    def resolved(at: datetime, raw_exit: float, reason: str, phase: str,
                 ambiguous: bool = False) -> Result:
        slip = execution.extra_stop_slippage_bp if reason == "STOP" else 0.0
        exit_price = raw_exit - price * slip / 10_000
        if exit_price <= 0:
            raise ValueError("declared stop slippage implies a nonpositive exit price")
        gross = (raw_exit / price - 1) * 10_000
        net = gross - execution.round_trip_cost_bp - slip
        return Result(**base, status="RESOLVED", exit_at=at, exit_reason=reason,
                      exit_phase=phase, exit_price_before_slippage=raw_exit,
                      exit_price=exit_price, gross_return_bp=gross,
                      entry_cost_bp=execution.round_trip_cost_bp / 2,
                      exit_cost_bp=execution.round_trip_cost_bp / 2,
                      stop_slippage_bp=slip, net_return_bp=net,
                      net_pnl=episode.entry_notional * net / 10_000,
                      exit_order_ambiguous=ambiguous)

    if first is None:
        return unresolved(episode.entry_at)
    at = episode.entry_at
    while at <= episode.expiry_at:
        bar = lookup.get(at)
        if bar is None:
            return unresolved(at)
        if at == episode.expiry_at:
            return resolved(at, bar.open, "TIME", "open")
        if policy != Policy.TIME:
            if bar.open <= stop:
                return resolved(at, bar.open, "STOP", "open")
            if policy == Policy.COMBINED and bar.open >= target:
                return resolved(at, target, "TARGET", "open")
            target_barrier = target if policy == Policy.COMBINED else None
            hit = _within_bar(bar, stop, target_barrier, path)
            if hit is not None:
                reason, raw_exit = hit
                ambiguous = (policy == Policy.COMBINED and bar.low <= stop
                             and bar.high >= target and stop < bar.open < target)
                return resolved(at, raw_exit, reason, "within_bar", ambiguous)
        at += MINUTE
    raise AssertionError("expiry should have resolved the episode")


def simulate_policies(bars: Iterable[Bar], episode: Episode, path: Path,
                      execution: Execution = Execution()) -> list[Result]:
    """Use the same episode, bars and path for all three submitted policies."""
    records = list(bars)
    return [simulate(records, episode, policy, path, execution) for policy in Policy]


def paired_difference_bp(left: Result, right: Result) -> float:
    """A within-episode return difference; unresolved pairs are never dropped."""
    matched_fields = ("episode_id", "symbol", "signal_at", "entry_at", "expiry_at",
                      "entry_notional", "entry_price", "stop_price", "target_price", "path",
                      "declared_round_trip_cost_bp", "declared_extra_stop_slippage_bp")
    if any(getattr(left, key) != getattr(right, key) for key in matched_fields):
        raise ValueError("paired results must share the same episode, path and declared execution configuration")
    if left.status != "RESOLVED" or right.status != "RESOLVED":
        raise ValueError("an unresolved pair has no return difference")
    return left.net_return_bp - right.net_return_bp
