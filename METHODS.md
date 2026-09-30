# Implemented research and execution rules

These rules describe **Path-Robust Risk Controls for Intraday Mean Reversion in
NSE Equities**. The M3 episode engine and M4 development pipeline retain exactly
three policies: time-only, stop-only and stop plus target, all with the same time
cap. Execution rules are assumptions, not observed fills. The bounded M4 replay
is development evidence; final empirical evaluation remains outstanding.

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
Indian calendar date. The M4 runner supplies the declared session calendar and
excludes the specified nonstandard session. A calendar-date check in the execution engine alone does
not establish a valid exchange session.

The actual entry price is that entry bar's open. The fixed stop and target equal
that price times their supplied multipliers. Thus delayed entry changes the
entry price and reanchors both barriers. The fixtures use 0.99 and 1.01 to make
arithmetic easy to verify; these are demonstration settings, not estimated market
parameters. The M4 rule derives the multipliers from past stock-return
volatility, as declared in `config/m4_pilot.json` and described below.

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
entry and exit. The episode engine resolves trade P&L. The M4 research layer also records
within-session cash debits and reserved proceeds, as described below; it does
not construct a marked-to-market equity curve.

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
They do not validate actual fill probability, liquidity, market capacity, net
profitability or out-of-sample stability. The M4 tests additionally examine
source parsing, past-only signal calculations, missing-history retention, matched
allocations and session cash conservation. These properties do not establish
that the supplied timestamps have the assumed meaning, that the sample is
representative or that a fitted strategy generalizes.


## Vendor input and bounded preparation

The vendor parser requires the explicit eight-field header
`<ticker>,<date>,<time>,<open>,<high>,<low>,<close>,<volume>`, optionally followed
by a ninth `<o/i>` or blank field name. Dates are MM/DD/YYYY and times HH:MM:SS.
The ninth value is retained without identifying its economic meaning. Prices
must be positive and finite, volume finite and nonnegative, and minute labels
strictly increasing. Headerless supplements, unexpected schemas, duplicates,
unsorted rows and inconsistent OHLC are rejected. The parser does not silently
sort, deduplicate, drop, forward-fill or invent rows.

Raw timestamps remain naive source labels during preparation. `as_bar` attaches
the assumed Indian time zone and either keeps an assumed minute-start label or
shifts an assumed minute-end label back one minute. This is a sensitivity check,
not supplier confirmation. Session filtering follows conversion. Neither a
successful parse nor the appearance of familiar trading hours establishes the
interval semantics, adjustment status or actual liquidity.

`prepare_pilot.py` stages only the configured compressed monthly stock/index
containers and streams selected members into a private SQLite database. It
records source-member identities, checksums, row counts and label diagnostics.
The parser holds one row at a time; SQLite uses a small page cache and disk-backed
temporary storage. Local archive containers and the database need disk space
even though the full CSV corpus is not extracted or held in memory.

## Past-only signal and matched episodes

At each declared decision time, a completed 15-minute close-to-close return uses
16 consecutive minute-start labels, from decision minus 16 minutes through
decision minus one minute. Both stock and index coverage must be complete.
The signal return is the stock log return minus the index log return.

The current residual is standardized against the mean and sample standard
deviation of the same-clock residual returns in exactly the preceding 20
calendar sessions. Missing history is retained as missing; an older valid
observation never replaces an unavailable session. No current or future return
enters that reference distribution. Insufficient warm-up, missing current or
historical windows, and zero scales are explicit ineligibility reasons.

The long-only entry threshold is z <= -2. The stop scale **v** is estimated
separately: it is the sample standard deviation of the stock's own 15-minute
same-clock log returns over those prior sessions, not the residual standard
deviation. Fixed barriers are entry price multiplied by exp(-v) and exp(1.5v).

Decisions occur every 30 minutes, beginning 30 minutes after the session opens.
The reference entry is at the open one minute after the decision and the expiry
is 15 minutes after entry. The declared session must accommodate entry and
expiry. Delay scenarios reanchor entry and both barriers without using future
coverage to decide whether the signal exists. All three policies use the same
entries, allocations and expiry within a delay scenario.

Each episode receives fixed entry notional `0.5 * C0 / N`, where C0 is reference
capital and N is the predeclared stock count. The pilot uses C0 = INR 100,000 and
N = 5, hence INR 10,000 per stock episode. Fractional positions are a research
assumption. Entries are not enlarged when another stock has no signal or missing
data, and the index is a signal benchmark rather than a traded hedge.

## Session accounting and common evaluability

The research layer debits each common entry batch's notionals and entry fees,
reserves the allocation through its common scheduled expiry, then releases net
exit proceeds. Early exits create no extra entry or reusable allocation within
the holding window. It checks available cash before entry, rejects insufficient
cash and verifies that closing cash equals opening cash plus summed net P&L.
Stop slippage is included once, through the effective exit price.

The M4 runner uses **independent session accounts initialized at C0**. Daily
return is net session P&L divided by C0. This is not a continuously funded
multi-day wealth process: it does not prove that losses can be carried across
all days while maintaining the common allocation. Do not compound these returns
or label their cumulative sum a self-financing portfolio equity curve. Although
`ResearchState` can accept six known opening-cash values, the pilot does not
orchestrate funded segments after missing account values.

A day is evaluable only when candidate windows, required histories and all six
policy/path accounts meet the declared rules. Invalid candidate coverage,
unresolved positions or insufficient common capital withhold numeric daily
returns for every scenario. A valid day with no signals has zero return; a day
with unknown signals is not a zero-trade day. Episode diagnostics remain
available even when the portfolio-day comparison is withheld. Exclusions and
resulting selection limits must be reported.

The code does not build minute-close marked-to-market equity, observed
within-minute equity, or a continuous drawdown series across unknown intervals.
Those are separate remaining tasks. Independent session cash checks do not
substitute for them.

## Frozen development protocol and remaining inference

`config/m4_pilot.json` is the declared M4 development configuration. It selects
January–March 2021 and the fixed five-stock universe before strategy outcomes,
with .NSEI as benchmark. Its calendar cites an official 2021 holiday source.
24 February is retained as a missing-history session and excluded from trading
because of the documented nonstandard session. This retrospective exclusion is
known before the pilot replay but not before the historical outage; outage-day
losses remain outside these estimates.

The protocol evaluates assumed start/end labels, both candle paths and seven
one-at-a-time cost/slippage/delay settings. It does not search thresholds or
select stocks by returns. Preserve the JSON and its recorded hash with each run;
a later change requires a dated version and a reason. The earlier
`reference_protocol.json` remains the M3 study record, including its historical
implementation-status fields.

The primary eventual contrast is combined-minus-time mean net daily return
under reference cost/delay and stop-first assumptions. Secondary contrasts are
stop-minus-time and combined-minus-stop. The latter measures adding this target
to this stop; it does not identify a target-only strategy or a complete
stop-target interaction.

`expected_shortfall` calculates the mean of exactly the worst 2.5% empirical
loss mass at 97.5% confidence, using fractional weighting at the boundary. It
expects losses, not returns. It is a descriptive sample calculation, not a claim
that a short tail is reliable. Calculate each policy's ES and then difference
them; ES of the paired differences answers a different question.

The full study still requires audited sample definition, resolved source
metadata, a funded portfolio/marked-equity design, sufficient evaluable history,
and the declared chronological development/validation/final-test process.
The 60/20/20 split and day-block inference belong to that later frozen evaluation,
not this short development replay. Do not inspect final-test strategy outcomes
before the final protocol freeze or report pilot contrasts as holdout inference.
