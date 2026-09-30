# Research pipeline and remaining work

The project retains the submitted title and exactly three exit policies. The
M4 development pilot integrates the existing execution engine with supplied
market data under stated assumptions. It is not the final experiment.

## Implemented components

| Component | Current capability | Remaining boundary |
| --- | --- | --- |
| Vendor parser | Streams the declared eight/nine-field CSV layout; validates symbols, chronology, prices and volume; retains raw timestamp labels. | Parsing does not establish time-zone/interval semantics, adjustments, liquidity or the meaning of the optional ninth field. |
| Selected-file preparation | Streams the frozen pilot's selected archive members into private SQLite; records provenance, checksums and row diagnostics. | This is not a complete audit of every delivered archive or permission to redistribute it. |
| Past-only signal | Completed 15-minute stock-minus-index return, prior 20 calendar sessions at the same clock time, z <= -2; separate stock-return volatility for barriers. | Missing history remains missing. Real-data semantics and a sufficient final sample still need confirmation. |
| Matched episodes | Same entries, fixed notionals and expiries across the three policies within each delay scenario. | A delayed scenario has a different entry schedule and reanchored barriers; it is not a different policy arm. |
| Execution | Both coherent candle paths; gaps, expiry precedence, declared costs and stop slippage; explicit unresolved outcomes. | OHLC does not identify actual price ordering, spreads, queue execution or market impact. |
| Session accounts | Cash reservation, entry-fee checks, net proceeds and conservation within a session. | The pilot resets to C0 each session; it is not a funded multi-day portfolio or marked-to-market equity simulation. |
| Descriptive risk utility | Fractional-boundary empirical expected shortfall. | A tested formula does not establish a statistically reliable tail estimate on a short pilot. |
| Reproduction | Frozen pilot configuration, deterministic checks, preparation/replay commands and Windows process-tree memory report. | Source-data permissions and metadata remain separate evidence requirements. |

The exact M4 specification is `config/m4_pilot.json`, declared before the first
strategy replay. It fixes five named examples for January–March 2021, start/end
label sensitivity, two candle paths and seven one-at-a-time execution settings.
It does not add strategies or search for a favourable sample. A new design
requires a new version and explanation rather than changing this record after
seeing its results.

## Interpretation of preliminary outputs

Keep three evidence types separate:

1. **Synthetic tests:** exact expected arithmetic and event order on constructed
   inputs. These include the M3 examples in `results/`.
2. **Input and integration evidence:** selected-file counts, hashes, parser
   diagnostics, eligibility/exclusion counts and reproducible execution.
3. **Conditional market development replay:** descriptive contrasts for the
   frozen pilot, under declared timestamps, calendar exclusions and fill rules.
   No final holdout or general NSE performance claim follows from this sample.

Retain raw/normalized prices, individual market trade ledgers and detailed daily
accounts only in excluded local data directories. Public aggregate outputs must
be clearly labelled and must not expose restricted price records. Record
unresolved days rather than reporting them as zero returns. The 24 February 2021
exclusion is a retrospective study decision, not a historically predictable
avoidance of outage losses.

## Work still required

| Stage | Completion evidence | Gate before proceeding |
| --- | --- | --- |
| Source and sample audit | Confirmed interval/time-zone semantics, session exceptions, coverage, adjustments, source precedence, permissions and defensible universe limits. | Do not call supplied labels or broad liquidity claims verified without supporting evidence. |
| Portfolio extension | Known opening cash across contiguous segments, reserved allocation, no borrowing, minute/daily sampled marked equity and explicit segment breaks. | Reconcile a continuous funded process; independent daily resets are insufficient. |
| Development review | Documented defects, missingness choices, sensitivity results and an independently reconciled ledger. | Changes must follow method/data concerns, not favourable outcomes. |
| Chronological validation | Predeclared 60/20/20 trading-day split, appropriate warm-up and no episodes crossing split boundaries. | Keep final-test strategy outcomes unopened during development and validation. |
| Final protocol freeze | Versioned code, source manifest, eligibility rules, parameters, costs, outputs and inferential plan. | Evaluate the final test once after this freeze; outcome-driven redesign needs a fresh untouched period. |
| Final inference | Common evaluable days, paired contrasts, sampled risk measures, exclusions and uncertainty that preserve matched/cross-stock dependence. | Sufficient history and effective loss-tail size; day blocks cannot span unknown intervals. |
| Independent review and report | Reconciled tables/figures, source-version checks, accurate claims, contribution evidence and reviewer access. | Resolve or disclose outstanding access and private-repository requirements. |

Daily returns in the full design use net P&L divided by fixed initial capital;
entry notionals do not compound with gains. Valid no-trade days belong in the
sample, but missing candidate data do not establish a valid no-trade day. Unknown
equity intervals cannot be joined into one drawdown record.

The eventual primary contrast is combined minus time-only mean net daily return
under stop-first, reference-cost and reference-delay assumptions. Stop-only minus
time-only and combined minus stop-only are secondary. Risk comparisons report
each policy's maximum drawdown and daily ES97.5 before interpreting differences,
with sampling frequency and effective tail count. Lower exposure and better
entry prediction are different explanations and must not be conflated.

The proposed group workstreams are data/signals, execution/testing, and
evaluation/writing, with a second member reviewing each. Named ownership and
completed contributions must be agreed and recorded in `CONTRIBUTORS.md` or a
linked contribution log. No person-specific completed work is inferred from
group membership.
