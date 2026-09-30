"""Past-only signals and fixed-capital daily accounts for the three-policy study.

The caller supplies one calendar session at a time, including sessions containing
missing data. It must determine the actual trading calendar and select the fixed
universe before evaluation. This module assumes start-labelled minute bars and
IST; parsing a timestamp does not establish those source-data conventions.

Only the last ``lookback_sessions`` session feature dictionaries are retained.
Missing windows remain missing: older valid sessions never replace them. A caller
can pass known opening cash for a contiguous equity segment; otherwise the day is
an independent account initialized at the declared reference capital. Neither
case compounds entry notionals. Early-exit proceeds remain unavailable until the
common scheduled expiry.

The pilot uses independent session accounts at C0. Its daily P&L/C0 and session
cash checks do not constitute a self-financing multi-day wealth simulation. This
module does not construct minute-close marked-to-market equity or orchestrate
funded segments after unknown cash. Do not infer cumulative portfolio drawdown,
compounded returns or a continuously funded strategy from independent replays.
"""

from collections import deque
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from math import exp, floor, fsum, isfinite, log
from statistics import mean, stdev
from typing import Mapping, Sequence

from .engine import Bar, Episode, Execution, IST, MINUTE, Path, Policy, Result, simulate_policies, validate_bars


@dataclass(frozen=True)
class ResearchConfig:
    universe: tuple[str, ...]
    index_symbol: str = ".NSEI"
    starting_capital: float = 100_000.0
    allocation_fraction: float = 0.5
    lookback_sessions: int = 20
    signal_window_minutes: int = 15
    first_decision_minutes_after_open: int = 30
    decision_interval_minutes: int = 30
    entry_delay_minutes: int = 1
    holding_minutes: int = 15
    entry_z_threshold: float = -2.0
    execution: Execution = Execution()

    def __post_init__(self) -> None:
        if (not isinstance(self.universe, tuple) or not self.universe
                or len(set(self.universe)) != len(self.universe)
                or any(not x or x.strip() != x for x in self.universe)):
            raise ValueError("universe must be a nonempty tuple of distinct symbols")
        if not self.index_symbol or self.index_symbol in self.universe:
            raise ValueError("the benchmark index must be separate from the stock universe")
        if not isfinite(self.starting_capital) or self.starting_capital <= 0:
            raise ValueError("starting_capital must be finite and positive")
        if not isfinite(self.allocation_fraction) or not 0 < self.allocation_fraction < 1:
            raise ValueError("allocation_fraction must lie strictly between zero and one")
        for name in ("lookback_sessions", "signal_window_minutes", "first_decision_minutes_after_open",
                     "decision_interval_minutes", "entry_delay_minutes", "holding_minutes"):
            value = getattr(self, name)
            if type(value) is not int or value < 1:
                raise ValueError(f"{name} must be a positive integer")
        if self.lookback_sessions < 2:
            raise ValueError("sample standard deviations require at least two prior sessions")
        if self.first_decision_minutes_after_open < self.signal_window_minutes + 1:
            raise ValueError("the complete close-to-close signal window must fit inside the session")
        if self.decision_interval_minutes < self.holding_minutes:
            raise ValueError("this account requires nonoverlapping scheduled holding windows")
        if not isfinite(self.entry_z_threshold):
            raise ValueError("entry_z_threshold must be finite")

    @property
    def entry_notional(self) -> float:
        return self.allocation_fraction * self.starting_capital / len(self.universe)


@dataclass(frozen=True)
class Feature:
    stock_return: float
    residual_return: float


@dataclass(frozen=True)
class Candidate:
    symbol: str
    decision_at: datetime
    status: str
    history_dates: tuple[date, ...]
    stock_return: float | None = None
    residual_return: float | None = None
    prior_residual_mean: float | None = None
    prior_residual_sd: float | None = None
    stock_volatility: float | None = None
    z_score: float | None = None


@dataclass(frozen=True)
class CashEvent:
    timestamp: datetime
    kind: str
    amount: float
    available_cash: float
    reserved_notional: float


@dataclass(frozen=True)
class DailyScenario:
    policy: str
    path: str
    status: str
    net_pnl: float | None
    return_on_reference_capital: float | None
    closing_cash: float | None
    minimum_available_cash: float | None
    cash_events: tuple[CashEvent, ...] = ()
    issue: str | None = None
    opening_cash: float | None = None


@dataclass(frozen=True)
class DayResult:
    session_date: date
    status: str
    candidates: tuple[Candidate, ...]
    episodes: tuple[Episode, ...]
    executions: tuple[Result, ...]
    scenarios: tuple[DailyScenario, ...]
    issues: tuple[str, ...]

    @property
    def common_evaluable(self) -> bool:
        return self.status == "EVALUABLE"


def _session_time(day: date, clock: time) -> datetime:
    if clock.tzinfo is not None or clock.second or clock.microsecond:
        raise ValueError("session bounds must be naive local times at minute boundaries")
    return datetime.combine(day, clock, IST)


def decision_times(day: date, config: ResearchConfig, session_open: time = time(9, 15),
                   session_close: time = time(15, 30)) -> tuple[datetime, ...]:
    """Calendar-based feasibility only; never inspect future observed coverage."""
    opening, closing = _session_time(day, session_open), _session_time(day, session_close)
    if opening >= closing:
        raise ValueError("session opening must precede its close on the same date")
    current = opening + config.first_decision_minutes_after_open * MINUTE
    output = []
    while current + (config.entry_delay_minutes + config.holding_minutes) * MINUTE < closing:
        output.append(current)
        current += config.decision_interval_minutes * MINUTE
    return tuple(output)


def _lookup(bars: Sequence[Bar], symbol: str, day: date) -> dict[datetime, Bar]:
    values = validate_bars(bars, symbol)
    if any(bar.timestamp.astimezone(IST).date() != day for bar in values):
        raise ValueError("process_day accepts bars from exactly one Indian calendar date")
    return {bar.timestamp: bar for bar in values}


def _feature(stock: Mapping[datetime, Bar], index: Mapping[datetime, Bar],
             decision: datetime, window: int) -> Feature | None:
    # A 15-minute close-to-close return needs the 16 consecutive start labels
    # decision-16, ..., decision-1. Endpoints alone do not establish coverage.
    labels = [decision - offset * MINUTE for offset in range(window + 1, 0, -1)]
    if any(label not in stock or label not in index for label in labels):
        return None
    stock_return = log(stock[labels[-1]].close / stock[labels[0]].close)
    index_return = log(index[labels[-1]].close / index[labels[0]].close)
    return Feature(stock_return, stock_return - index_return)


def _account(results: Sequence[Result], config: ResearchConfig,
             policy: Policy, path: Path, opening_cash: float) -> DailyScenario:
    """Keep exit proceeds reserved until expiry; enforce cash before entry fees."""
    selected = [r for r in results if r.policy == policy.value and r.path == path.value]
    if any(r.status != "RESOLVED" for r in selected):
        return DailyScenario(policy.value, path.value, "UNRESOLVED", None, None, None, None,
                             issue="UNRESOLVED_POSITION", opening_cash=opening_cash)
    batches: dict[datetime, list[Result]] = {}
    for result in selected:
        batches.setdefault(result.entry_at, []).append(result)
    cash, minimum, previous_expiry = opening_cash, opening_cash, None
    events = []
    for entry, batch in sorted(batches.items()):
        expiry = batch[0].expiry_at
        if any(r.expiry_at != expiry for r in batch) or (previous_expiry and previous_expiry > entry):
            raise ValueError("portfolio accounting requires common expiry and nonoverlapping batches")
        notional = fsum(r.entry_notional for r in batch)
        entry_fees = fsum(r.entry_notional * r.entry_cost_bp / 10_000 for r in batch)
        debit = notional + entry_fees
        if debit > cash + 1e-8:
            return DailyScenario(policy.value, path.value, "UNRESOLVED", None, None, None, minimum,
                                 tuple(events), "INSUFFICIENT_CASH_FOR_COMMON_ENTRIES", opening_cash)
        cash -= debit
        minimum = min(minimum, cash)
        events.append(CashEvent(entry, "ENTRY", -debit, cash, notional))
        proceeds = fsum(r.entry_notional * (r.exit_price / r.entry_price)
                        - r.entry_notional * r.exit_cost_bp / 10_000 for r in batch)
        # Fractional shares = entry_notional / entry_price. The exit price already
        # includes extra stop slippage, so that penalty must not be debited twice.
        cash += proceeds
        if cash < -1e-8:
            return DailyScenario(policy.value, path.value, "UNRESOLVED", None, None, None, cash,
                                 tuple(events), "NEGATIVE_CASH_AFTER_COSTS", opening_cash)
        minimum = min(minimum, cash)
        events.append(CashEvent(expiry, "COMMON_EXPIRY_RELEASE", proceeds, cash, 0.0))
        previous_expiry = expiry
    pnl = fsum(r.net_pnl for r in selected)
    if abs(cash - (opening_cash + pnl)) > max(1e-7, abs(cash) * 1e-12):
        raise AssertionError("daily cash conservation failed")
    return DailyScenario(policy.value, path.value, "EVALUABLE", pnl,
                         pnl / config.starting_capital, cash, minimum, tuple(events), opening_cash=opening_cash)


class ResearchState:
    """Sequential feature state. Pass every eligible calendar session, even empty.

    ``evaluate=False`` advances history without opening positions. Use this for
    history warmup or an explicitly excluded development segment. History across
    a chronological split is valid; future dates and reordered/repeated dates are
    rejected. The caller, not observed data availability, determines session dates.
    Supply all six known ``opening_cash[(policy.value, path.value)]`` amounts to
    continue a funded equity segment. If omitted, this is an independent daily
    account at C0, not a claim of continuous equity. An unresolved day breaks the
    known-equity segment; this feature state cannot infer missing account value.
    """

    def __init__(self, config: ResearchConfig):
        self.config = config
        self._history: deque[tuple[date, dict[tuple[str, time], Feature | None]]] = deque(
            maxlen=config.lookback_sessions)
        self._last_date: date | None = None

    @property
    def history_dates(self) -> tuple[date, ...]:
        return tuple(day for day, _ in self._history)

    def process_day(self, session_date: date, stock_bars: Mapping[str, Sequence[Bar]],
                    index_bars: Sequence[Bar], *, session_open: time = time(9, 15),
                    session_close: time = time(15, 30), evaluate: bool = True,
                    opening_cash: Mapping[tuple[str, str], float] | None = None) -> DayResult:
        if not isinstance(session_date, date) or isinstance(session_date, datetime):
            raise ValueError("session_date must be a date")
        if self._last_date is not None and session_date <= self._last_date:
            raise ValueError("sessions must be strictly chronological without repeats")
        config = self.config
        keys = {(policy.value, path.value) for path in Path for policy in Policy}
        cash_by_scenario = dict(opening_cash) if opening_cash is not None else {
            key: config.starting_capital for key in keys}
        if set(cash_by_scenario) != keys or any(
                value is None or not isfinite(value) or value < 0 for value in cash_by_scenario.values()):
            raise ValueError("opening_cash requires all six scenarios with known finite nonnegative cash")
        if set(stock_bars) - set(config.universe):
            raise ValueError("stock inputs contain symbols outside the fixed universe")
        stocks = {symbol: _lookup(stock_bars.get(symbol, ()), symbol, session_date)
                  for symbol in config.universe}
        index = _lookup(index_bars, config.index_symbol, session_date)
        decisions = decision_times(session_date, config, session_open, session_close)
        features, candidates, episodes, executions = {}, [], [], []
        for decision in decisions:
            for symbol in config.universe:
                key = (symbol, decision.time())
                current = _feature(stocks[symbol], index, decision, config.signal_window_minutes)
                features[key] = current
                common = dict(symbol=symbol, decision_at=decision, history_dates=self.history_dates,
                              stock_return=current.stock_return if current else None,
                              residual_return=current.residual_return if current else None)
                if current is None:
                    candidate = Candidate(**common, status="MISSING_CURRENT_WINDOW")
                elif len(self._history) < config.lookback_sessions:
                    candidate = Candidate(**common, status="WARMUP")
                else:
                    prior = [session_features.get(key) for _, session_features in self._history]
                    if any(value is None for value in prior):
                        candidate = Candidate(**common, status="MISSING_HISTORY_WINDOW")
                    else:
                        residual_mean = mean(value.residual_return for value in prior)
                        residual_sd = stdev(value.residual_return for value in prior)
                        stock_sd = stdev(value.stock_return for value in prior)
                        stats = dict(prior_residual_mean=residual_mean,
                                     prior_residual_sd=residual_sd, stock_volatility=stock_sd)
                        if residual_sd == 0 or stock_sd == 0:
                            candidate = Candidate(**common, **stats, status="UNDEFINED_SCALE")
                        else:
                            z_score = (current.residual_return - residual_mean) / residual_sd
                            candidate = Candidate(**common, **stats, z_score=z_score,
                                                  status="SIGNAL" if z_score <= config.entry_z_threshold else "NO_SIGNAL")
                candidates.append(candidate)
                if evaluate and candidate.status == "SIGNAL":
                    entry = decision + config.entry_delay_minutes * MINUTE
                    episode = Episode(f"{session_date.isoformat()}_{symbol}_{decision:%H%M}", symbol,
                                      decision, entry, entry + config.holding_minutes * MINUTE,
                                      exp(-candidate.stock_volatility), exp(1.5 * candidate.stock_volatility),
                                      config.entry_notional)
                    episodes.append(episode)
                    # This happens after the signal decision. Absent future bars
                    # cannot suppress the episode; the engine reports unresolved.
                    bars = list(stocks[symbol].values())
                    for path in Path:
                        executions.extend(simulate_policies(bars, episode, path, config.execution))

        invalid = sorted({candidate.status for candidate in candidates
                          if candidate.status not in ("SIGNAL", "NO_SIGNAL")})
        issues = []
        if not evaluate:
            status = "HISTORY_ONLY"
        elif not decisions:
            status = "NO_ELIGIBLE_DECISION_TIMES"
            issues.append(status)
        elif len(self._history) < config.lookback_sessions:
            status = "WARMUP"
            issues.extend(invalid)
        elif invalid:
            status = "INCOMPLETE_CANDIDATE_COVERAGE"
            issues.extend(invalid)
        elif any(result.status != "RESOLVED" for result in executions):
            status = "UNRESOLVED_POSITIONS"
            issues.append("UNRESOLVED_POSITION")
        else:
            status = "EVALUABLE"

        accounts = tuple(_account(executions, config, policy, path, cash_by_scenario[(policy.value, path.value)])
                         for path in Path for policy in Policy)
        if status == "EVALUABLE" and any(account.status != "EVALUABLE" for account in accounts):
            status = "INSUFFICIENT_COMMON_CAPITAL"
            issues.extend(sorted({account.issue for account in accounts if account.issue}))
        if status != "EVALUABLE":
            # Keep episode-level diagnostics, but never report a partial/zero
            # portfolio return for a day failing the common six-scenario mask.
            accounts = tuple(DailyScenario(policy.value, path.value, status, None, None, None, None,
                                           issue=";".join(issues) or status,
                                           opening_cash=cash_by_scenario[(policy.value, path.value)])
                             for path in Path for policy in Policy)
        self._history.append((session_date, features))
        self._last_date = session_date
        return DayResult(session_date, status, tuple(candidates), tuple(episodes),
                         tuple(executions), accounts, tuple(issues))


def expected_shortfall(losses: Sequence[float], confidence: float = 0.975) -> float:
    """Mean of the worst (1-confidence) empirical loss mass, fractional boundary.

    Pass losses (negative portfolio returns), not returns. Every observation has
    mass 1/n. This is a descriptive sample statistic; a short tail is not made
    reliable by interpolation. Missing observations must be resolved upstream.
    """
    if not isfinite(confidence) or not 0 < confidence < 1:
        raise ValueError("confidence must lie strictly between zero and one")
    values = list(losses)
    if not values or any(value is None or not isfinite(value) for value in values):
        raise ValueError("expected shortfall requires nonempty finite losses without missing values")
    values.sort(reverse=True)
    tail_count = (1 - confidence) * len(values)
    whole = floor(tail_count)
    fraction = tail_count - whole
    numerator = fsum(values[:whole])
    if fraction:
        numerator += fraction * values[whole]
    return numerator / tail_count
