"""Deterministic synthetic checks; these are not market-data findings."""

import unittest
from dataclasses import replace
from datetime import date, datetime, time, timedelta
from math import exp, log
from statistics import stdev

from path_robust.engine import Bar, Execution, IST, MINUTE, Path, Policy
from path_robust.research import ResearchConfig, ResearchState, decision_times, expected_shortfall


BASE = date(2024, 1, 1)
CLOSE = time(10, 10)
CONFIG = ResearchConfig(("STOCK_A", "STOCK_B"))


def session(day, stock_return=0.0, index_return=0.0, config=CONFIG,
            close=CLOSE, fill=100.0, both_hit=False):
    """Construct complete synthetic sessions with exact scheduled return windows."""
    decisions = decision_times(day, config, session_close=close)
    opening = datetime.combine(day, time(9, 15), IST)
    closing = datetime.combine(day, close, IST)

    def series(symbol, value):
        end_closes = {d - MINUTE: 100 * exp(value) for d in decisions}
        start_closes = {d - (config.signal_window_minutes + 1) * MINUTE for d in decisions}
        entries = {d + config.entry_delay_minutes * MINUTE for d in decisions}
        output, at = [], opening
        while at < closing:
            closing_price = end_closes.get(at, 100.0 if at in start_closes else fill)
            high, low = max(fill, closing_price), min(fill, closing_price)
            if both_hit and at in entries and symbol != config.index_symbol:
                high, low = max(high, fill * 1.1), min(low, fill * 0.9)
            output.append(Bar(symbol, at, fill, high, low, closing_price))
            at += MINUTE
        return output

    return ({symbol: series(symbol, stock_return) for symbol in config.universe},
            series(config.index_symbol, index_return))


def warm_state(config=CONFIG, close=CLOSE, pairs=None):
    state = ResearchState(config)
    pairs = pairs or [((-1 if i % 2 == 0 else 1) * .001, 0.0)
                      for i in range(config.lookback_sessions)]
    for i, (stock_return, index_return) in enumerate(pairs):
        day = BASE + timedelta(days=i)
        stocks, index = session(day, stock_return, index_return, config, close)
        result = state.process_day(day, stocks, index, session_close=close, evaluate=False)
        assert result.status == "HISTORY_ONLY"
    return state


def evaluate(state, stock_return=-.01, index_return=0.0, close=CLOSE, **kwargs):
    day = BASE + timedelta(days=state.config.lookback_sessions)
    stocks, index = session(day, stock_return, index_return, state.config, close, **kwargs)
    return state.process_day(day, stocks, index, session_close=close)


class SignalTests(unittest.TestCase):
    def test_defaults_match_submitted_signal_and_three_policy_protocol(self):
        self.assertEqual(CONFIG.lookback_sessions, 20)
        self.assertEqual(CONFIG.signal_window_minutes, 15)
        self.assertEqual(CONFIG.entry_z_threshold, -2)
        self.assertEqual(CONFIG.entry_delay_minutes, 1)
        self.assertEqual(CONFIG.holding_minutes, 15)
        result = evaluate(warm_state())
        self.assertEqual({r.policy for r in result.executions}, {p.value for p in Policy})
        self.assertEqual(len(result.executions), 2 * 3 * 2)

    def test_signal_uses_twenty_prior_same_clock_sessions_only(self):
        result = evaluate(warm_state())
        first = result.candidates[0]
        self.assertAlmostEqual(first.prior_residual_mean, 0.0, places=12)
        self.assertAlmostEqual(first.prior_residual_sd, stdev([-.001, .001] * 10), places=12)
        self.assertEqual(first.history_dates, tuple(BASE + timedelta(days=i) for i in range(20)))
        self.assertNotIn(result.session_date, first.history_dates)
        self.assertEqual(first.status, "SIGNAL")

    def test_barrier_volatility_is_stock_sd_not_residual_sd(self):
        pairs = [((i - 10) * .001, (i - 10) * .0009) for i in range(20)]
        result = evaluate(warm_state(pairs=pairs))
        candidate = result.candidates[0]
        self.assertAlmostEqual(candidate.stock_volatility, stdev(x[0] for x in pairs), places=12)
        self.assertAlmostEqual(candidate.prior_residual_sd, stdev(x[0] - x[1] for x in pairs), places=12)
        self.assertAlmostEqual(candidate.stock_volatility / candidate.prior_residual_sd, 10)
        self.assertAlmostEqual(result.episodes[0].stop_multiplier, exp(-candidate.stock_volatility))
        self.assertAlmostEqual(result.episodes[0].target_multiplier, exp(1.5 * candidate.stock_volatility))

    def test_future_price_perturbation_does_not_change_signal_or_episode(self):
        baseline = evaluate(warm_state())
        state = warm_state()
        day = BASE + timedelta(days=20)
        stocks, index = session(day, -.01)
        decision = baseline.candidates[0].decision_at
        changed = {symbol: [replace(b, open=200, high=210, low=190, close=205)
                            if b.timestamp >= decision else b for b in bars]
                   for symbol, bars in stocks.items()}
        changed_index = [replace(b, open=300, high=310, low=290, close=300)
                         if b.timestamp >= decision else b for b in index]
        result = state.process_day(day, changed, changed_index, session_close=CLOSE)
        self.assertEqual(result.candidates, baseline.candidates)
        self.assertEqual(result.episodes, baseline.episodes)
        self.assertNotEqual(result.executions[0].entry_price, baseline.executions[0].entry_price)

    def test_close_window_has_exact_sixteen_labels_and_no_current_candle(self):
        state = warm_state()
        day = BASE + timedelta(days=20)
        stocks, index = session(day, -.01)
        decision = decision_times(day, CONFIG, session_close=CLOSE)[0]
        # Remove a bar strictly before the window; this must not affect the signal.
        stocks["STOCK_A"] = [b for b in stocks["STOCK_A"] if b.timestamp != decision - 17 * MINUTE]
        result = state.process_day(day, stocks, index, session_close=CLOSE)
        self.assertEqual(result.candidates[0].status, "SIGNAL")
        self.assertAlmostEqual(result.candidates[0].stock_return, -.01)

    def test_manual_endpoint_prices_distinguish_off_by_one_return_windows(self):
        state = warm_state()
        day = BASE + timedelta(days=20)
        stocks, index = session(day, 0)

        def set_closes(bars, prices):
            output = []
            for bar in bars:
                closing = prices.get(bar.timestamp.time(), bar.close)
                output.append(replace(bar, close=closing, high=max(bar.open, closing),
                                      low=min(bar.open, closing)))
            return output

        # Explicit times and different neighbouring values avoid deriving the
        # expected answer from the implementation's endpoint-selection rule.
        stocks["STOCK_A"] = set_closes(stocks["STOCK_A"], {
            time(9, 29): 100, time(9, 30): 125, time(9, 43): 140,
            time(9, 44): 90, time(9, 45): 300})
        index = set_closes(index, {
            time(9, 29): 200, time(9, 30): 400, time(9, 43): 999,
            time(9, 44): 220, time(9, 45): 900})
        result = state.process_day(day, stocks, index, session_close=CLOSE)
        first = result.candidates[0]
        self.assertEqual(first.decision_at, datetime.combine(day, time(9, 45), IST))
        self.assertAlmostEqual(first.stock_return, log(90 / 100))
        self.assertAlmostEqual(first.residual_return, log(90 / 100) - log(220 / 200))

    def test_missing_interior_signal_bar_is_not_replaced_by_endpoint_return(self):
        state = warm_state()
        day = BASE + timedelta(days=20)
        stocks, index = session(day, -.01)
        missing = datetime.combine(day, time(9, 35), IST)
        stocks["STOCK_A"] = [b for b in stocks["STOCK_A"] if b.timestamp != missing]
        result = state.process_day(day, stocks, index, session_close=CLOSE)
        self.assertEqual(result.candidates[0].status, "MISSING_CURRENT_WINDOW")
        self.assertEqual(result.status, "INCOMPLETE_CANDIDATE_COVERAGE")
        self.assertTrue(all(r.net_pnl is None for r in result.scenarios))

    def test_history_missing_session_is_not_replaced_by_older_valid_session(self):
        state = warm_state()
        # The next session is explicitly missing; the fixed 20-session window
        # must retain it even though 20 older valid observations once existed.
        missing_day = BASE + timedelta(days=20)
        state.process_day(missing_day, {}, (), session_close=CLOSE, evaluate=False)
        day = BASE + timedelta(days=21)
        stocks, index = session(day, -.01)
        result = state.process_day(day, stocks, index, session_close=CLOSE)
        self.assertTrue(all(c.status == "MISSING_HISTORY_WINDOW" for c in result.candidates))
        self.assertEqual(len(state.history_dates), 20)
        self.assertEqual(result.candidates[0].history_dates[0], BASE + timedelta(days=1))
        self.assertTrue(all(r.net_pnl is None for r in result.scenarios))

    def test_current_completed_window_changes_future_history_only(self):
        left, right = warm_state(), warm_state()
        before_left, before_right = evaluate(left, -.01), evaluate(right, -.02)
        self.assertEqual(before_left.candidates[0].stock_volatility,
                         before_right.candidates[0].stock_volatility)
        day = BASE + timedelta(days=21)
        stocks, index = session(day, -.01)
        later_left = left.process_day(day, stocks, index, session_close=CLOSE)
        later_right = right.process_day(day, stocks, index, session_close=CLOSE)
        self.assertNotEqual(later_left.candidates[0].stock_volatility,
                            later_right.candidates[0].stock_volatility)

    def test_warmup_day_never_becomes_zero_profit_day(self):
        state = ResearchState(CONFIG)
        stocks, index = session(BASE, -.01)
        result = state.process_day(BASE, stocks, index, session_close=CLOSE)
        self.assertEqual(result.status, "WARMUP")
        self.assertFalse(result.episodes)
        self.assertTrue(all(r.net_pnl is None for r in result.scenarios))

    def test_flat_prior_scale_is_explicit_not_false_zero_trade_day(self):
        result = evaluate(warm_state(pairs=[(0.0, 0.0)] * 20))
        self.assertEqual(result.status, "INCOMPLETE_CANDIDATE_COVERAGE")
        self.assertEqual(result.candidates[0].status, "UNDEFINED_SCALE")
        self.assertTrue(all(r.net_pnl is None for r in result.scenarios))

    def test_split_warmup_does_not_trade_and_past_history_can_cross_split(self):
        state = warm_state()
        day = BASE + timedelta(days=20)
        stocks, index = session(day, -.01)
        training = state.process_day(day, stocks, index, session_close=CLOSE, evaluate=False)
        self.assertTrue(any(c.status == "SIGNAL" for c in training.candidates))
        self.assertFalse(training.episodes)
        test_day = day + timedelta(days=1)
        stocks, index = session(test_day, -.02)
        holdout = state.process_day(test_day, stocks, index, session_close=CLOSE)
        self.assertEqual(holdout.candidates[0].history_dates[-1], day)
        self.assertTrue(all(d < test_day for d in holdout.candidates[0].history_dates))

    def test_reversed_or_repeated_session_is_rejected(self):
        state = warm_state()
        for day in (BASE, BASE + timedelta(days=19)):
            stocks, index = session(day)
            with self.assertRaisesRegex(ValueError, "chronological"):
                state.process_day(day, stocks, index, session_close=CLOSE)

    def test_other_date_or_wrong_universe_is_rejected(self):
        state = ResearchState(CONFIG)
        stocks, index = session(BASE + timedelta(days=1))
        with self.assertRaisesRegex(ValueError, "calendar date"):
            state.process_day(BASE, stocks, index)
        with self.assertRaisesRegex(ValueError, "fixed universe"):
            state.process_day(BASE, {"UNDECLARED": []}, [])


class PortfolioTests(unittest.TestCase):
    def test_common_notional_cash_conservation_and_fractional_shares(self):
        result = evaluate(warm_state(), fill=101.3)
        self.assertTrue(result.common_evaluable)
        self.assertEqual({e.entry_notional for e in result.episodes}, {25_000})
        for scenario in result.scenarios:
            self.assertAlmostEqual(scenario.net_pnl, -75)
            self.assertAlmostEqual(scenario.return_on_reference_capital, -.00075)
            self.assertAlmostEqual(scenario.closing_cash, 99_925)
            self.assertAlmostEqual(scenario.minimum_available_cash, 49_962.5)
            self.assertAlmostEqual(fsum_events(scenario), scenario.net_pnl)

    def test_early_exits_release_capital_only_at_common_expiry(self):
        result = evaluate(warm_state(), both_hit=True)
        self.assertTrue(result.common_evaluable)
        self.assertTrue(any(r.exit_at < r.expiry_at for r in result.executions))
        for scenario in result.scenarios:
            self.assertEqual([e.kind for e in scenario.cash_events], ["ENTRY", "COMMON_EXPIRY_RELEASE"])
            self.assertEqual(scenario.cash_events[1].timestamp, result.episodes[0].expiry_at)
            self.assertEqual(scenario.cash_events[0].reserved_notional, 50_000)

    def test_stop_slippage_debited_exactly_once_in_cash_account(self):
        plain = evaluate(warm_state(), both_hit=True)
        config = replace(CONFIG, execution=Execution(15, 10))
        penalized = evaluate(warm_state(config), both_hit=True)
        for left, right in zip(plain.scenarios, penalized.scenarios):
            selected = [r for r in plain.executions if (r.policy, r.path) == (left.policy, left.path)]
            stop_count = sum(r.exit_reason == "STOP" for r in selected)
            self.assertAlmostEqual(right.net_pnl - left.net_pnl, -25 * stop_count)
            self.assertAlmostEqual(right.closing_cash, 100_000 + right.net_pnl)

    def test_missing_entry_does_not_suppress_signal_and_invalidates_all_scenarios(self):
        state = warm_state()
        day = BASE + timedelta(days=20)
        stocks, index = session(day, -.01)
        entry = datetime.combine(day, time(9, 46), IST)
        stocks["STOCK_A"] = [b for b in stocks["STOCK_A"] if b.timestamp != entry]
        result = state.process_day(day, stocks, index, session_close=CLOSE)
        self.assertEqual(len(result.episodes), 2)
        self.assertEqual(result.status, "UNRESOLVED_POSITIONS")
        self.assertTrue(any(r.issue == "MISSING_ENTRY_BAR" for r in result.executions))
        self.assertTrue(all(s.net_pnl is None for s in result.scenarios))

    def test_missing_expiry_invalidates_day_even_if_stops_already_resolved(self):
        state = warm_state()
        day = BASE + timedelta(days=20)
        stocks, index = session(day, -.01, both_hit=True)
        expiry = datetime.combine(day, time(10, 1), IST)
        stocks["STOCK_A"] = [b for b in stocks["STOCK_A"] if b.timestamp != expiry]
        result = state.process_day(day, stocks, index, session_close=CLOSE)
        self.assertTrue(any(r.status == "RESOLVED" for r in result.executions))
        self.assertTrue(any(r.status == "UNRESOLVED" for r in result.executions))
        self.assertTrue(all(s.net_pnl is None for s in result.scenarios))

    def test_fully_eligible_no_signal_day_has_zero_pnl_for_every_scenario(self):
        result = evaluate(warm_state(), stock_return=0)
        self.assertTrue(result.common_evaluable)
        self.assertFalse(result.episodes)
        self.assertTrue(all(s.net_pnl == 0 and s.closing_cash == 100_000 for s in result.scenarios))

    def test_absent_stock_is_not_silently_removed_from_fixed_universe(self):
        state = warm_state()
        day = BASE + timedelta(days=20)
        stocks, index = session(day, 0)
        del stocks["STOCK_B"]
        result = state.process_day(day, stocks, index, session_close=CLOSE)
        self.assertEqual(result.status, "INCOMPLETE_CANDIDATE_COVERAGE")
        self.assertTrue(all(s.net_pnl is None for s in result.scenarios))

    def test_allocation_does_not_increase_when_only_one_stock_signals(self):
        state = warm_state()
        day = BASE + timedelta(days=20)
        stocks, index = session(day, -.01)
        quiet, _ = session(day, 0)
        stocks["STOCK_B"] = quiet["STOCK_B"]
        result = state.process_day(day, stocks, index, session_close=CLOSE)
        self.assertEqual(len(result.episodes), 1)
        self.assertEqual(result.episodes[0].entry_notional, 25_000)

    def test_insufficient_cash_prevents_all_scenario_portfolio_claims(self):
        config = replace(CONFIG, execution=Execution(30_000, 0))
        result = evaluate(warm_state(config))
        self.assertEqual(result.status, "INSUFFICIENT_COMMON_CAPITAL")
        self.assertTrue(all(s.net_pnl is None for s in result.scenarios))

    def test_multiple_batches_do_not_compound_entry_notional(self):
        result = evaluate(warm_state(close=time(15, 30)), close=time(15, 30))
        self.assertEqual(len(result.episodes), 22)
        self.assertEqual({e.entry_notional for e in result.episodes}, {25_000})
        self.assertTrue(result.common_evaluable)
        for scenario in result.scenarios:
            self.assertAlmostEqual(scenario.net_pnl, -825)
            self.assertTrue(all(e.available_cash >= 0 for e in scenario.cash_events))

    def test_known_cash_carries_across_days_without_reinvesting_gains(self):
        state = warm_state()
        first = evaluate(state)
        cash = {(s.policy, s.path): s.closing_cash for s in first.scenarios}
        day = BASE + timedelta(days=21)
        stocks, index = session(day, -.02)
        second = state.process_day(day, stocks, index, session_close=CLOSE, opening_cash=cash)
        self.assertTrue(second.common_evaluable)
        self.assertEqual({e.entry_notional for e in second.episodes}, {25_000})
        for scenario in second.scenarios:
            self.assertAlmostEqual(scenario.opening_cash, 99_925)
            self.assertAlmostEqual(scenario.closing_cash, 99_850)
            self.assertAlmostEqual(scenario.return_on_reference_capital, -.00075)

    def test_one_scenario_cannot_borrow_to_preserve_common_entries(self):
        state = warm_state()
        day = BASE + timedelta(days=20)
        stocks, index = session(day, -.01)
        cash = {(p.value, path.value): 100_000 for path in Path for p in Policy}
        cash[(Policy.STOP.value, Path.LOW_FIRST.value)] = 10_000
        result = state.process_day(day, stocks, index, session_close=CLOSE, opening_cash=cash)
        self.assertEqual(result.status, "INSUFFICIENT_COMMON_CAPITAL")
        self.assertTrue(all(s.net_pnl is None for s in result.scenarios))

    def test_missing_cash_cannot_resume_a_continuous_segment(self):
        state = warm_state()
        day = BASE + timedelta(days=20)
        stocks, index = session(day, -.01)
        cash = {(p.value, path.value): 100_000 for path in Path for p in Policy}
        cash[(Policy.STOP.value, Path.LOW_FIRST.value)] = None
        with self.assertRaisesRegex(ValueError, "known finite"):
            state.process_day(day, stocks, index, session_close=CLOSE, opening_cash=cash)


def fsum_events(scenario):
    return sum(event.amount for event in scenario.cash_events)


class CalendarAndMetricsTests(unittest.TestCase):
    def test_schedule_requires_expiry_strictly_inside_actual_session(self):
        decisions = decision_times(BASE, CONFIG)
        self.assertEqual(len(decisions), 11)
        self.assertEqual(decisions[0].time(), time(9, 45))
        self.assertEqual(decisions[-1].time(), time(14, 45))
        self.assertFalse(decision_times(BASE, CONFIG, session_close=time(10, 1)))
        self.assertEqual(len(decision_times(BASE, CONFIG, session_close=time(10, 2))), 1)

    def test_delay_moves_actual_entry_and_checks_session_feasibility(self):
        config = replace(CONFIG, entry_delay_minutes=5)
        result = evaluate(warm_state(config))
        self.assertEqual(result.episodes[0].entry_at.time(), time(9, 50))
        self.assertEqual(result.episodes[0].expiry_at.time(), time(10, 5))
        self.assertFalse(decision_times(BASE, config, session_close=time(10, 5)))

    def test_no_eligible_schedule_is_not_zero_trade_day(self):
        state = warm_state()
        day = BASE + timedelta(days=20)
        stocks, index = session(day, -.01, close=time(10, 1))
        result = state.process_day(day, stocks, index, session_close=time(10, 1))
        self.assertEqual(result.status, "NO_ELIGIBLE_DECISION_TIMES")
        self.assertTrue(all(s.net_pnl is None for s in result.scenarios))

    def test_sample_es_includes_fractional_boundary_mass(self):
        # At n=6 and confidence=.75, tail mass is 1.5 observations.
        self.assertAlmostEqual(expected_shortfall([10, 8, 6, 4, 2, 0], .75), (10 + .5 * 8) / 1.5)
        self.assertAlmostEqual(expected_shortfall(list(range(100)), .975), (99 + 98 + .5 * 97) / 2.5)

    def test_short_tail_es_is_sample_worst_loss_and_preserves_sign(self):
        self.assertAlmostEqual(expected_shortfall([.1, -.02, -.03], .975), .1)
        self.assertAlmostEqual(expected_shortfall([-.1, -.2], .975), -.1)

    def test_es_refuses_missing_nonfinite_or_empty_samples(self):
        for values in ([], [None], [float("nan")], [float("inf")]):
            with self.assertRaises(ValueError):
                expected_shortfall(values)
        for confidence in (0, 1, -1, float("nan")):
            with self.assertRaises(ValueError):
                expected_shortfall([1], confidence)

    def test_invalid_overlapping_configuration_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "nonoverlapping"):
            replace(CONFIG, decision_interval_minutes=10)
        with self.assertRaisesRegex(ValueError, "sample standard"):
            replace(CONFIG, lookback_sessions=1)
        with self.assertRaisesRegex(ValueError, "separate"):
            replace(CONFIG, index_symbol="STOCK_A")


if __name__ == "__main__":
    unittest.main()
