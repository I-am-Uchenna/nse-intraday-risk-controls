# Implemented execution rules

This is the initial execution component of **Path-Robust Risk Controls for
Intraday Mean Reversion in NSE Equities**. The following rules describe the code
that currently runs. They are not claims of observed fills.

## Inputs and timing

Each bar has `symbol,timestamp,open,high,low,close`. Timestamps identify the start
of the minute, include an explicit UTC offset, and lie on minute boundaries.
Prices must be finite and positive, with low no greater than either open or close
and high no smaller than either. Bars must be strictly chronological for a single
instrument. Duplicate or unsorted records are rejected rather than silently fixed.
The input adapter preserves gaps.

An episode supplies a signal-completion time, entry time, expiry time, stop
multiplier, target multiplier and entry notional. Entry must be at least one
minute after signal completion. Entry and expiry are bar-open events on the same
Indian calendar date. Exchange-session validation remains part of the pending
market-data audit; a calendar-date check alone does not establish a valid session.

The actual entry price is that entry bar's open. The fixed stop and target equal
that price times their supplied multipliers. Thus delayed entry changes the
entry price and reanchors both barriers. The fixtures use 0.99 and 1.01 to make
arithmetic easy to verify; these are demonstration settings, not estimated market
parameters. The provisional empirical rule instead derives the multipliers from
past volatility, as described in `config/reference_protocol.json`.

## Event order

1. If the current required bar is absent, return `UNRESOLVED` immediately.
2. If its start is the scheduled expiry, close at its open. Do not inspect its
   later high or low for a barrier exit. No extra stop slippage applies to a time exit.
3. Otherwise, an enabled stop breached at the open fills at that open. This
   permits losses beyond the stop threshold after an adverse gap.
4. An enabled target breached at the open fills at the target, with no assumed
   favourable price improvement.
5. If there is no opening exit, traverse either O-L-H-C or O-H-L-C. Exit at the
   first enabled barrier crossed, including an exact touch. The same path is
   used for all three policies in a scenario.
6. Continue to the next minute if no exit occurs.

Time-only enables no barrier. Stop-only enables just the stop. The combined
policy enables both. Every policy retains the same expiry. All entry-candle
extrema may be used because entry occurs at that candle's open. Extrema in bars
before entry or after the expiry open cannot trigger an exit.

When the open lies between both barriers and both fall inside the candle's
range, the combined exit is flagged as order-ambiguous. The path scenarios
resolve it differently without pretending to identify the actual sequence.
An opening target gap resolves before the subsequent low even if that same
candle later also falls below the stop.

For a `within_bar` exit, the ledger's `exit_at` is the start timestamp of the
containing minute, not an observed event time. `exit_phase` distinguishes it
from an exit at the open. The exact within-minute exit time and holding duration
cannot be recovered from the candle and must not be inferred from that label.

## Accounting in one episode

All basis points are relative to entry notional. Let P be the entry price, X the
exit price before extra slippage, c the round-trip cost in bp, and s the extra
stop cost in bp (zero if the exit reason is not STOP).

```text
gross_return_bp = 10,000 * (X / P - 1)
effective_exit_price = X - P * s / 10,000
net_return_bp = gross_return_bp - c - s
net_pnl = entry_notional * net_return_bp / 10,000
```

The ledger records both X and the effective exit price. `gross_return_bp` is
before the separately recorded stop penalty; using the effective exit price and
then subtracting s again would double-count it. Costs are split equally between
entry and exit. The current code resolves trade P&L only: it does not create an
intraday cash ledger or an equity curve.

Identical c cancels from a matched difference of completed trade returns. It
still changes each absolute return. Stop-specific s can change the relative
comparison because not every policy or path triggers a stop. This algebra does
not by itself establish cancellation for a portfolio risk statistic.

Missing entry, active-period or expiry bars are not filled forward. The result
records the missing timestamp, keeps the entry cost if the entry is known, and
leaves total return and P&L null. `paired_difference_bp` refuses to compute a
difference if either result is unresolved or the episodes, paths or declared
execution configurations differ. The ledger retains both declared cost settings,
including the extra stop penalty even when no stop occurs; a zero realised stop
penalty does not establish that two scenarios used the same assumption.

This starter adopts strict active-period coverage for all policies, including
time-only. If entry and expiry opens are known but an interior minute is missing,
time-only endpoint P&L is mathematically identifiable. The code nevertheless
withholds that outcome under its common coverage rule because the full monitored
path is incomplete. The rule is a conservative data-quality convention; it must
not be described as a proof that the endpoint return is unknowable. Any empirical
complete-case comparison requires disclosure of exclusions and potential bias.

## What the checks do and do not establish

The synthetic examples establish that these event-order and arithmetic rules
produce their specified outcomes. The unit tests also reject malformed input.
They do not validate a trading signal, actual fill probability, liquidity,
market capacity, net profitability, expected shortfall, or out-of-sample stability.
The code needs a reviewed real-data adapter, past-only signal implementation,
portfolio layer and empirical evaluation before any such claims are considered.
