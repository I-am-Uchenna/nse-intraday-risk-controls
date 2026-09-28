# Remaining research pipeline

The supplied market data still require an audit and integration. This plan keeps
the submitted three-policy comparison fixed. Any feasibility-driven change must
be recorded before inspecting final-test outcomes.

| Stage | Current status | Required output |
| --- | --- | --- |
| File inventory and data audit | Pending integration | Instrument/date coverage, timestamp convention, time zone, duplicates, gaps, OHLC errors, adjustment information and available liquidity fields. |
| Past-only entry signals | Not implemented | Stock-minus-index completed 15-minute log returns, standardized with the preceding 20 sessions at the same clock window; missing or zero-variance history marked ineligible. |
| Shared entry episodes | Caller-supplied only | Common decision times, entry delays, fixed stop/target multipliers, common expiries and notional allocations. |
| Three-policy execution | Implemented | Resolved/unresolved ledgers under both paths and the declared costs/slippage. |
| Portfolio accounting | Not implemented | Reserved allocation until common expiry; no early-exit reinvestment; cash-feasibility flags; daily returns and minute/daily sampled equity. |
| Chronological evaluation | Not implemented | Development/validation/final-test dates, frozen configuration, aligned comparisons, uncertainty and disclosed exclusions. |

The provisional signal is long-only: every 30 minutes starting 30 minutes after
session open, calculate the completed 15-minute stock log return minus the index
log return. Compare it with the same-clock-window distribution from the prior 20
sessions. Enter when its z-score is at most -2. The initial entry delay is one
minute and the holding cap is 15 minutes. A prior-only stock volatility measure
sets nontrailing barriers through exp(-v) and exp(1.5v). These choices are
provisional until the data audit; no parameter optimum is claimed.

Each policy must use the same signal-derived entries and allocations within a
delay scenario. An episode that closes early does not free capital for a new
entry. Missing future records must not be used to decide eligibility or increase
allocations to the remaining observations.

The initial chronological split is 60% development, 20% validation and 20% final
testing by trading day, subject to available history. The final test is evaluated
after the design is frozen; it is not omitted. Past observations may warm up
indicators, but trading episodes cannot cross splits. Perturbing future bars must
not change an earlier signal; this property needs tests once signals exist.

The primary comparison is combined minus time-only in mean daily net return
under stop-first, reference-cost and reference-delay assumptions. Stop-only
minus time-only and combined minus stop-only are secondary contrasts. A target
without a stop is outside the submitted scope.

Daily returns will use daily net P&L divided by fixed starting capital, including
valid zero-trade days. Unresolved portfolio days must stay visibly unresolved;
unknown equity intervals cannot be joined into one continuous drawdown record.
Known-start uninterrupted segments require separate labels if restarted.

Planned risk outputs are sampled maximum drawdown and 97.5% daily expected
shortfall, with the number of evaluable days and effective tail observations.
Any uncertainty calculation must preserve matched policy and cross-stock
dependence. Blocks of days cannot span data gaps. Expected-shortfall differences
must be computed by taking each policy's expected shortfall and then differencing,
not by taking expected shortfall of daily policy differences.

The final report must distinguish absolute loss/profit from relative improvement,
and lower exposure from a better entry signal. Neither a favourable synthetic
example nor a favourable result under one path establishes an executable edge.

Before empirical results are reported, add tests for signal chronology, account
conservation, allocation reservation, absence of borrowing, session boundaries,
corporate-action handling, and daily alignment. Record the actual data audit,
implementation changes and group contributions as they occur.
