# Initial execution checks

**SYNTHETIC / NOT MARKET DATA.**

These hand-constructed prices test declared execution rules. They do not establish
profitability, a market effect, a confidence interval, or expected strategy risk.

The main fixture enters at 100, stops at 99, targets 101 and expires 15 minutes
later at an opening price of 100.5. Its entry candle has low 98.5 and high 101.5.
Round-trip costs are 15 bp of entry notional unless a case states otherwise.

| Example | Assumed path | Time-only net bp | Stop-only net bp | Combined net bp | Combined minus time bp |
| --- | --- | ---: | ---: | ---: | ---: |
| both_hit | O-L-H-C | +35.000000 | -115.000000 | -115.000000 | -150.000000 |
| both_hit | O-H-L-C | +35.000000 | -115.000000 | +85.000000 | +50.000000 |
| common_cost_25bp | O-L-H-C | +25.000000 | -125.000000 | -125.000000 | -150.000000 |
| common_cost_25bp | O-H-L-C | +25.000000 | -125.000000 | +75.000000 | +50.000000 |
| stop_slippage_10bp | O-L-H-C | +35.000000 | -125.000000 | -125.000000 | -160.000000 |
| stop_slippage_10bp | O-H-L-C | +35.000000 | -125.000000 | +85.000000 | +50.000000 |
| opening_stop_gap | O-L-H-C | +35.000000 | -215.000000 | -215.000000 | -250.000000 |
| opening_stop_gap | O-H-L-C | +35.000000 | -215.000000 | -215.000000 | -250.000000 |
| opening_target_gap | O-L-H-C | +35.000000 | -115.000000 | +85.000000 | +50.000000 |
| opening_target_gap | O-H-L-C | +35.000000 | -115.000000 | +85.000000 | +50.000000 |
| expiry_precedence | O-L-H-C | -215.000000 | -215.000000 | -215.000000 | +0.000000 |
| expiry_precedence | O-H-L-C | -215.000000 | -215.000000 | -215.000000 | +0.000000 |
| missing_active_minute | O-L-H-C | UNRESOLVED | UNRESOLVED | UNRESOLVED | UNRESOLVED |
| missing_active_minute | O-H-L-C | UNRESOLVED | UNRESOLVED | UNRESOLVED | UNRESOLVED |
| missing_after_early_exit | O-L-H-C | UNRESOLVED | -115.000000 | -115.000000 | UNRESOLVED |
| missing_after_early_exit | O-H-L-C | UNRESOLVED | -115.000000 | +85.000000 | UNRESOLVED |
| missing_entry | O-L-H-C | UNRESOLVED | UNRESOLVED | UNRESOLVED | UNRESOLVED |
| missing_entry | O-H-L-C | UNRESOLVED | UNRESOLVED | UNRESOLVED | UNRESOLVED |
| delay_two_minutes | O-L-H-C | +44.880240 | +44.880240 | +44.880240 | +0.000000 |
| delay_two_minutes | O-H-L-C | +44.880240 | +44.880240 | +44.880240 | +0.000000 |

In the both-hit fixture, combined-minus-time changes from -150 bp under
O-L-H-C to +50 bp under O-H-L-C. The ordering assumption changes the ranking
while the observed OHLC is identical. This is a demonstration, not a measured
frequency or effect in NSE data.

Increasing identical costs from 15 to 25 bp reduces each completed return by
10 bp and leaves matched differences unchanged. An extra 10 bp on stop exits
changes only the outcomes that actually exit at a stop.

UNRESOLVED is stored as null in JSON and a blank numeric cell in CSV, never
as a zero. An already closed policy can be resolved while its time-only
benchmark fails the strict active-period coverage rule. Its paired difference
is then withheld. Time-only endpoint P&L may still be arithmetically known
when only interior bars are absent; withholding it is a declared data-quality
rule, not a statement that endpoint arithmetic is impossible.

The two paths are coherent scenarios and do not reconstruct actual tick order
or bound portfolio drawdown. Touch fills remain assumptions.

## Next empirical step

Audit the supplied market data, map its timestamps and instruments, and implement
past-only signals and portfolio accounting before any market performance study.
