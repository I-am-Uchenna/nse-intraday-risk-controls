import unittest
from dataclasses import replace
from datetime import datetime, timedelta

from path_robust.engine import (
    Bar, Episode, Execution, IST, Path, Policy, paired_difference_bp,
    simulate, simulate_policies, validate_bars,
)

BASE = datetime(2024, 1, 2, 10, 0, tzinfo=IST)


def bar(minute, opening=100.0, high=100.4, low=99.6, close=100.0):
    return Bar("SYNTHETIC", BASE + timedelta(minutes=minute), opening, high, low, close)


def episode(**changes):
    value = Episode("test", "SYNTHETIC", BASE - timedelta(minutes=1), BASE,
                    BASE + timedelta(minutes=2), .99, 1.01)
    return replace(value, **changes)


def normal_bars():
    return [bar(0), bar(1), bar(2, 100.5, 100.8, 100.2, 100.5)]


class ExecutionTests(unittest.TestCase):
    def test_both_hit_low_first_known_returns(self):
        bars = [bar(0, 100, 101.5, 98.5, 100)] + normal_bars()[1:]
        values = simulate_policies(bars, episode(), Path.LOW_FIRST)
        for result, expected in zip(values, (35, -115, -115)):
            self.assertAlmostEqual(result.net_return_bp, expected)
        self.assertTrue(values[2].exit_order_ambiguous)

    def test_both_hit_high_first_changes_combined_only(self):
        bars = [bar(0, 100, 101.5, 98.5, 100)] + normal_bars()[1:]
        values = simulate_policies(bars, episode(), Path.HIGH_FIRST)
        for result, expected in zip(values, (35, -115, 85)):
            self.assertAlmostEqual(result.net_return_bp, expected)
        self.assertEqual(values[1].exit_reason, "STOP")
        self.assertEqual(values[2].exit_reason, "TARGET")

    def test_open_stop_gap_fills_at_open_not_stop(self):
        bars = [bar(0), bar(1, 98, 99.5, 97.5, 98.5), normal_bars()[2]]
        for path in Path:
            result = simulate(bars, episode(), Policy.COMBINED, path)
            self.assertEqual(result.exit_price, 98)
            self.assertEqual(result.exit_phase, "open")
            self.assertAlmostEqual(result.net_return_bp, -215)

    def test_target_gap_uses_target_without_favourable_price_improvement(self):
        bars = [bar(0), bar(1, 102, 103, 98, 101), normal_bars()[2]]
        for path in Path:
            result = simulate(bars, episode(), Policy.COMBINED, path)
            self.assertEqual(result.exit_price, 101)
            self.assertEqual(result.exit_phase, "open")
            self.assertFalse(result.exit_order_ambiguous)
            self.assertAlmostEqual(result.net_return_bp, 85)

    def test_expiry_open_precedes_stop_gap_and_has_no_stop_slippage(self):
        bars = [bar(0), bar(1), bar(2, 98, 105, 97, 104)]
        for result in simulate_policies(bars, episode(), Path.HIGH_FIRST, Execution(15, 10)):
            self.assertEqual(result.exit_reason, "TIME")
            self.assertEqual(result.exit_price, 98)
            self.assertEqual(result.stop_slippage_bp, 0)
            self.assertAlmostEqual(result.net_return_bp, -215)

    def test_extremes_in_expiry_bar_do_not_trigger_barriers(self):
        bars = [bar(0), bar(1), bar(2, 100.5, 105, 95, 96)]
        for result in simulate_policies(bars, episode(), Path.LOW_FIRST):
            self.assertEqual(result.exit_reason, "TIME")
            self.assertAlmostEqual(result.net_return_bp, 35)

    def test_pre_entry_extremes_cannot_trigger_exit(self):
        bars = [bar(-1, 100, 120, 80, 100)] + normal_bars()
        result = simulate(bars, episode(), Policy.COMBINED, Path.LOW_FIRST)
        self.assertEqual(result.exit_reason, "TIME")
        self.assertAlmostEqual(result.net_return_bp, 35)

    def test_delayed_entry_uses_new_open_and_reanchors_barriers(self):
        bars = [bar(0, 100, 110, 90, 100), bar(1, 102, 102.4, 101.6, 102),
                bar(2, 102.5, 103, 102.3, 102.7)]
        later = episode(entry_at=BASE + timedelta(minutes=1))
        result = simulate(bars, later, Policy.COMBINED, Path.LOW_FIRST)
        self.assertEqual(result.entry_price, 102)
        self.assertAlmostEqual(result.stop_price, 100.98)
        self.assertEqual(result.exit_reason, "TIME")

    def test_single_stop_touch_does_not_depend_on_path(self):
        bars = [bar(0, 100, 100.5, 99, 100)] + normal_bars()[1:]
        for path in Path:
            result = simulate(bars, episode(), Policy.COMBINED, path)
            self.assertEqual(result.exit_reason, "STOP")
            self.assertAlmostEqual(result.net_return_bp, -115)
            self.assertFalse(result.exit_order_ambiguous)

    def test_single_target_touch_does_not_depend_on_path(self):
        bars = [bar(0, 100, 101, 99.5, 100)] + normal_bars()[1:]
        for path in Path:
            result = simulate(bars, episode(), Policy.COMBINED, path)
            self.assertEqual(result.exit_reason, "TARGET")
            self.assertAlmostEqual(result.net_return_bp, 85)

    def test_missing_entry_is_unresolved_not_a_zero_trade(self):
        result = simulate(normal_bars()[1:], episode(), Policy.TIME, Path.LOW_FIRST)
        self.assertEqual(result.status, "UNRESOLVED")
        self.assertEqual(result.issue, "MISSING_ENTRY_BAR")
        self.assertIsNone(result.entry_price)
        self.assertIsNone(result.net_return_bp)
        self.assertIsNone(result.net_pnl)

    def test_missing_active_interval_cannot_be_bridged(self):
        bars = [normal_bars()[0], normal_bars()[2]]
        for result in simulate_policies(bars, episode(), Path.LOW_FIRST):
            self.assertEqual(result.status, "UNRESOLVED")
            self.assertEqual(result.unresolved_at, BASE + timedelta(minutes=1))
            self.assertEqual(result.entry_cost_bp, 7.5)
            self.assertIsNone(result.net_return_bp)

    def test_missing_expiry_is_not_filled_at_previous_close(self):
        result = simulate(normal_bars()[:2], episode(), Policy.TIME, Path.LOW_FIRST)
        self.assertEqual(result.status, "UNRESOLVED")
        self.assertEqual(result.unresolved_at, episode().expiry_at)

    def test_missing_after_a_resolved_exit_does_not_reopen_position(self):
        bars = [bar(0, 100, 101.5, 98.5, 100), normal_bars()[2]]
        time, stop, combined = simulate_policies(bars, episode(), Path.LOW_FIRST)
        self.assertEqual(time.status, "UNRESOLVED")
        self.assertEqual(stop.status, "RESOLVED")
        self.assertEqual(combined.status, "RESOLVED")
        with self.assertRaises(ValueError):
            paired_difference_bp(combined, time)

    def test_common_costs_cancel_from_a_matched_difference(self):
        bars = [bar(0, 100, 101.5, 98.5, 100)] + normal_bars()[1:]
        differences = []
        for cost in (5, 15, 25):
            time, _, combined = simulate_policies(bars, episode(), Path.HIGH_FIRST, Execution(cost))
            differences.append(paired_difference_bp(combined, time))
        for difference in differences:
            self.assertAlmostEqual(difference, 50)

    def test_extra_stop_slippage_reduces_only_stop_triggered_returns(self):
        bars = [bar(0, 100, 101.5, 98.5, 100)] + normal_bars()[1:]
        for path in Path:
            base = simulate_policies(bars, episode(), path, Execution(15, 0))
            adverse = simulate_policies(bars, episode(), path, Execution(15, 10))
            for before, after in zip(base, adverse):
                expected = 10 if before.exit_reason == "STOP" else 0
                self.assertAlmostEqual(before.net_return_bp - after.net_return_bp, expected)
                self.assertAlmostEqual(after.exit_price,
                                       after.exit_price_before_slippage - expected / 100)

    def test_costs_charged_once_and_pnl_matches_notional(self):
        result = simulate(normal_bars(), episode(entry_notional=20_000), Policy.TIME, Path.LOW_FIRST)
        self.assertEqual(result.entry_cost_bp + result.exit_cost_bp, 15)
        self.assertAlmostEqual(result.net_pnl, 70)

    def test_different_path_results_cannot_be_paired_as_one_scenario(self):
        a = simulate(normal_bars(), episode(), Policy.TIME, Path.LOW_FIRST)
        b = simulate(normal_bars(), episode(), Policy.COMBINED, Path.HIGH_FIRST)
        with self.assertRaises(ValueError):
            paired_difference_bp(b, a)

    def test_different_declared_costs_cannot_be_mistaken_for_policy_effect(self):
        time = simulate(normal_bars(), episode(), Policy.TIME, Path.LOW_FIRST, Execution(15, 0))
        combined = simulate(normal_bars(), episode(), Policy.COMBINED, Path.LOW_FIRST, Execution(25, 0))
        self.assertEqual(time.exit_reason, combined.exit_reason)
        self.assertEqual(time.exit_price, combined.exit_price)
        self.assertAlmostEqual(time.net_return_bp - combined.net_return_bp, 10)
        with self.assertRaisesRegex(ValueError, "declared execution configuration"):
            paired_difference_bp(combined, time)

    def test_different_declared_stop_penalties_are_rejected_even_if_neither_stops(self):
        time = simulate(normal_bars(), episode(), Policy.TIME, Path.LOW_FIRST, Execution(15, 0))
        combined = simulate(normal_bars(), episode(), Policy.COMBINED, Path.LOW_FIRST, Execution(15, 10))
        self.assertEqual(time.stop_slippage_bp, 0)
        self.assertEqual(combined.stop_slippage_bp, 0)
        self.assertEqual(time.net_return_bp, combined.net_return_bp)
        self.assertEqual(combined.declared_extra_stop_slippage_bp, 10)
        with self.assertRaisesRegex(ValueError, "declared execution configuration"):
            paired_difference_bp(combined, time)


class ValidationTests(unittest.TestCase):
    def test_invalid_ohlc_is_rejected(self):
        with self.assertRaises(ValueError):
            bar(0, 100, 99, 98, 98.5)

    def test_nonfinite_price_is_rejected(self):
        with self.assertRaises(ValueError):
            bar(0, float("nan"))

    def test_zero_price_is_rejected(self):
        with self.assertRaises(ValueError):
            bar(0, 0, 100, 0, 100)

    def test_duplicate_bar_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_bars([bar(0), bar(0)], "SYNTHETIC")

    def test_unsorted_bars_are_not_silently_sorted(self):
        with self.assertRaises(ValueError):
            simulate([bar(1), bar(0)], episode(), Policy.TIME, Path.LOW_FIRST)

    def test_wrong_symbol_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_bars([replace(bar(0), symbol="OTHER")], "SYNTHETIC")

    def test_timezone_and_minute_boundary_are_required(self):
        for timestamp in (BASE.replace(tzinfo=None), BASE + timedelta(seconds=1)):
            with self.assertRaises(ValueError):
                replace(bar(0), timestamp=timestamp)

    def test_entry_cannot_use_the_signal_completion_open(self):
        with self.assertRaises(ValueError):
            episode(signal_at=BASE)

    def test_overnight_episode_is_rejected(self):
        with self.assertRaises(ValueError):
            episode(expiry_at=BASE + timedelta(days=1))

    def test_invalid_barrier_multipliers_are_rejected(self):
        for changes in ({"stop_multiplier": 1}, {"target_multiplier": 1},
                        {"target_multiplier": float("nan")}):
            with self.assertRaises(ValueError):
                episode(**changes)

    def test_negative_costs_are_rejected(self):
        with self.assertRaises(ValueError):
            Execution(-1, 0)


if __name__ == "__main__":
    unittest.main()
