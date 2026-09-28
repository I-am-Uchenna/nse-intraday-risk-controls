"""Hand-constructed examples. SYNTHETIC; NOT MARKET DATA."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from .engine import Bar, Episode, Execution, IST

BASE = datetime(2024, 1, 2, 10, 0, tzinfo=IST)
LABEL = "SYNTHETIC / NOT MARKET DATA"


@dataclass(frozen=True)
class Case:
    name: str
    purpose: str
    bars: tuple[Bar, ...]
    episode: Episode
    execution: Execution


def _bar(minute, opening=100.2, high=100.4, low=99.8, close=100.2):
    return Bar("SYNTHETIC", BASE + timedelta(minutes=minute), opening, high, low, close)


def cases() -> list[Case]:
    quiet = [_bar(0, 100, 100.4, 99.6, 100)]
    quiet += [_bar(i) for i in range(1, 15)]
    quiet += [_bar(15, 100.5, 100.8, 100.2, 100.5),
              _bar(16, 100.8, 101, 100.5, 100.8)]
    both = [_bar(0, 100, 101.5, 98.5, 100)] + quiet[1:]
    def case(name, purpose, bars, costs=Execution(), delay=1):
        entry = BASE + timedelta(minutes=delay - 1)
        entry_episode = Episode(name, "SYNTHETIC", BASE - timedelta(minutes=1),
                                entry, entry + timedelta(minutes=15), .99, 1.01)
        return Case(name, purpose, tuple(bars), entry_episode, costs)

    stop_gap = quiet.copy()
    stop_gap[1] = _bar(1, 98, 99.5, 97.5, 98.5)
    target_gap = quiet.copy()
    target_gap[1] = _bar(1, 102, 103, 98, 101)
    expiry_gap = quiet.copy()
    expiry_gap[15] = _bar(15, 98, 105, 97, 104)
    return [
        case("both_hit", "Same OHLC produces opposite combined-versus-time ranking.", both),
        case("common_cost_25bp", "A common extra 10 bp changes levels, not matched differences.",
             both, Execution(25, 0)),
        case("stop_slippage_10bp", "Extra stop cost changes policies that actually stop.",
             both, Execution(15, 10)),
        case("opening_stop_gap", "An adverse gap fills at 98 rather than the stop at 99.", stop_gap),
        case("opening_target_gap", "Opening target gap fills at 101 rather than 102.", target_gap),
        case("expiry_precedence", "Expiry open comes before gaps and later barrier touches.",
             expiry_gap, Execution(15, 10)),
        case("missing_active_minute", "An unknown active minute cannot be treated as zero return.",
             quiet[:1] + quiet[2:]),
        case("missing_after_early_exit", "A resolved barrier trade cannot repair missing benchmark path coverage.",
             both[:1] + both[2:]),
        case("missing_entry", "Missing entry price prevents a resolved position outcome.", quiet[1:]),
        case("delay_two_minutes", "A later entry ignores earlier extrema and recalculates barriers.",
             both, delay=2),
    ]
