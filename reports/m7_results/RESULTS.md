The entry signal earns 0.2200–0.6860 bp of reference capital per evaluable day before costs, against
assumed fees of 2.6063–2.6959 bp per day. The fee exceeds that gross in every recorded cell.
Time-only, stop-only and stop-and-target are three ways of losing money: every recorded net mean is
negative, between -2.6985 and -2.0100 bp per day.

## Results

Gross return in this table is the recorded net return plus the declared 15 bp round-trip fee on
entry notional. The fee uses one tenth of reference capital per episode. Time-only is the entry held
to the common 15-minute cap. Stop-only and stop-and-target change that exit. The table reports all
three.

| Stage | Label | Exit | Days | Gross bp/day | Fee bp/day | Net bp/day |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| Development | start | Time-only | 360 | 0.3179 | 2.6542 | -2.3362 |
| Development | start | Stop-only | 360 | 0.0617 | 2.6542 | -2.5925 |
| Development | start | Stop and target | 360 | 0.0855 | 2.6542 | -2.5687 |
| Development | end | Time-only | 381 | 0.2200 | 2.6063 | -2.3863 |
| Development | end | Stop-only | 381 | 0.1128 | 2.6063 | -2.4935 |
| Development | end | Stop and target | 381 | 0.0926 | 2.6063 | -2.5137 |
| Validation | start | Time-only | 148 | 0.6860 | 2.6959 | -2.0100 |
| Validation | start | Stop-only | 148 | 0.4095 | 2.6959 | -2.2864 |
| Validation | start | Stop and target | 148 | -0.0025 | 2.6959 | -2.6985 |
| Validation | end | Time-only | 148 | 0.5842 | 2.6351 | -2.0510 |
| Validation | end | Stop-only | 148 | 0.1841 | 2.6351 | -2.4511 |
| Validation | end | Stop and target | 148 | 0.1987 | 2.6351 | -2.4365 |

Combined minus time-only, at reference execution, is negative under both candle orderings in every
recorded cell. On open-low-high-close ordering the four estimates are development start labels
-0.2325 bp/day (360 days); development end labels -0.1273 bp/day (381 days); validation start labels
-0.6885 bp/day (148 days); validation end labels -0.3855 bp/day (148 days).

Both stop-based exits have lower 97.5 percent expected shortfall than time-only, and deeper
daily-close funded drawdown than time-only, in every stage and timestamp label under
open-low-high-close ordering. On the validation start-label accounts the shortfall is 13.3647 bp for
time-only, 11.6941 bp for stop-only and 11.8599 bp for stop and target. Daily-close drawdown on
those accounts is 2.9851 percent, 3.3891 percent and 4.0140 percent of starting capital.

Reference episodes that touch both barriers inside one active candle: development start labels 0 of
637; development end labels 0 of 662; validation start labels 0 of 266; validation end labels 1 of
260.

These figures cover development (1 January 2021–17 October 2022) and validation (18 October 2022–25
May 2023). Run 20261111T081528Z-fzxevfhy on 11 November 2026 reproduced the validation gross, fee
and net figures. The largest numeric difference in that comparison is 0.

## Limitations

These statements describe the recorded development and validation samples. Development start labels
use 360 of 443 scheduled sessions. Development end labels use 381 of 443 scheduled sessions.
Validation start labels use 148 of 148 scheduled sessions. Validation end labels use 148 of 148
scheduled sessions. Sessions that fail the complete-case rule are omitted. They are not entered as
zero returns. The five stocks were fixed before the recorded outcomes. They are not a random sample
of the exchange, and the two partitions are not pooled.

The 15 bp round-trip fee is a declared scenario charged on entry notional. It is not a measured
spread, impact or queue. A minute candle does not identify which barrier printed first.
Open-low-high-close and open-high-low-close are two fill scenarios. Counts of candles that touch
both barriers do not recover historical ticks, and they do not establish path robustness beyond this
sample.

The nominal 95 percent moving-block intervals for combined minus time-only, using five-session
blocks and open-low-high-close ordering, are development start labels [-0.4410, 0.0770]; development
end labels [-0.3269, 0.1299]; validation start labels [-1.7037, -0.0809]; validation end labels
[-1.2170, 0.1695]. Synthetic diagnostics for this procedure show undercoverage, so the intervals
stay exploratory. An interval that excludes zero is not a confirmed population effect. No economic
adoption threshold was set in advance.

Expected shortfall uses a thin tail: development start labels 9.00 days; development end labels
9.525 days; validation start labels 3.70 days; validation end labels 3.70 days. Leave-one-day-out
ranges in the saved tables are sensitivities. They are not confidence intervals, and they do not
show whether the policy ranking survives deletion of one shared worst day. The public aggregates do
not contain the daily series that check would need. Funded drawdown follows cash and marked
positions through time. It is a different account path from the independent-session mean and from
expected shortfall. A lower shortfall beside a deeper drawdown is two results, not one.

The final partition, 26 May–29 December 2023, has not been evaluated. Run 20261111T081528Z-fzxevfhy
records final_test_evaluated as false. The statements in Results are not an estimate of that
partition, of other stocks, or of other cost schedules.

## Sources

Group 17838, 12 November 2026. Built from results/peer_review_20261022/gross_net_returns.csv, the
development_20261001 and validation_20261018 aggregate tables, and results/m7_validation_20261111
(run 20261111T081528Z-fzxevfhy). No price file is read. Regenerate with python
scripts/m7_results_narrative.py.
