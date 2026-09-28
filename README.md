# Path-Robust Risk Controls for Intraday Mean Reversion in NSE Equities

Student Group 17838 | MScFE 690 Capstone

This repository contains the initial execution code for a comparison of three
exit policies: **time-only, stop-only, and combined stop-loss and profit-target
exits**. The research question is whether the latter two improve net returns or
downside risk relative to a fixed holding period, and whether any benefits remain
under conservative execution assumptions.

## Current status

The minute-bar execution core and deterministic synthetic checks are implemented.
Market-data audit and integration are pending. The supplied data are not included
here. Signal generation, portfolio accounting and out-of-sample inference remain
planned work. No result in this repository is a market profitability estimate.

The code accepts a predetermined entry episode, applies all three policies to
that same episode, and reports resolved or unresolved outcomes. It does **not**
claim to test the entire proposed strategy or verify that supplied entry signals
were calculated without future information.

## Run

Use Python 3.10 or newer. No third-party packages are required for the current code.

```text
python scripts/run_checks.py
```

This runs the unit tests and regenerates the checked-in synthetic outputs. To
regenerate only the examples:

```text
python scripts/run_examples.py
```

Run these commands from the repository root. The scripts also work with an
absolute path to the Python executable.

## Initial findings

**All prices and results below are SYNTHETIC / NOT MARKET DATA.**

One constructed episode enters at 100, sets a stop at 99 and a target at 101, and
has a scheduled exit 15 minutes later at 100.5. Its first candle contains both
barriers. At 15 bp round-trip cost:

| Assumed price order | Time-only net bp | Stop-only net bp | Combined net bp |
| --- | ---: | ---: | ---: |
| Open-low-high-close | +35 | -115 | -115 |
| Open-high-low-close | +35 | -115 | +85 |

The combined-minus-time difference changes from -150 to +50 bp without changing
the candle data. This demonstrates why the proposed empirical comparison needs
explicit path assumptions. It does not establish how frequently this occurs in
NSE stocks or which policy will perform better.

Other constructed cases check gap fills, expiry precedence, missing records,
delayed entries, common-cost cancellation and additional stop slippage. See
[initial findings](results/initial_findings.md), the
[complete trade ledger](results/synthetic_examples.csv),
[paired comparisons](results/synthetic_comparisons.csv), and
[machine-readable summary](results/synthetic_summary.json).

## Files

| File | Purpose |
| --- | --- |
| `src/path_robust/engine.py` | Validated bars and episodes; three-policy execution; explicit unresolved outcomes. |
| `src/path_robust/data.py` | CSV schema and validation for one instrument's bar stream. |
| `src/path_robust/fixtures.py` | Hand-constructed example inputs. |
| `tests/` | Execution and input-validation tests with independently specified expected outcomes. |
| `examples/` | Regenerated synthetic inputs and episode specifications. |
| `results/` | Regenerated synthetic ledgers, paired differences, summary and test report. |
| `config/reference_protocol.json` | Provisional study settings and implementation status. |
| `METHODS.md` | Exact interpretation of the implemented execution rules. |
| `PIPELINE.md` | Remaining signal, data, accounting and evaluation work. |

## Interpretation and limitations

- The paths O-L-H-C and O-H-L-C are coherent scenarios, not recovered tick paths
  or universal bounds on portfolio drawdown.
- A touched target is treated as filled under an assumption. Order queues,
  spread, market impact and capacity are not observed from OHLC.
- Barriers are fixed after entry. The engine is long-only and checks that each
  episode is within one Indian calendar date. The market-data adapter must also
  validate the actual exchange session and special trading days.
- A missing required bar produces `UNRESOLVED`, with no numeric return. A gap
  after an already completed exit does not invalidate that completed trade, but
  a matched difference is withheld when its benchmark fails the coverage rule.
  The starter requires complete active-period minute coverage even for time-only:
  its endpoint P&L can sometimes be calculated across an interior gap, but is
  withheld under this strict comparability rule. This is an explicit data-quality
  choice, not a claim that endpoint arithmetic is impossible.
- Costs are declared scenarios, not a claim about verified NSE fees. The current
  reference is 15 bp of entry notional per round trip, plus optional stop slippage.
- The engine does not generate new entries or recycle early-exit capital. A
  later portfolio layer must enforce common allocations, reserved capital and
  the absence of implicit borrowing.

## Research sources

The distinction between a candle's observed price range and its unobserved order
is discussed by Stanislaus Maier-Paape and Andreas Platen in
["Backtest of Trading Systems on Candle Charts," *IFTA Journal*, 2016, pp. 10-17](https://www.ifta.org/assets/docs/d_ifta_journal_16.pdf).
The present core implements the project's declared scenarios; it is not a
reproduction of that paper's full algorithm.

Related theoretical work includes Tim Leung and Xin Li,
["Optimal Mean Reversion Trading with Transaction Costs and Stop-Loss Exit"](https://arxiv.org/abs/1411.5062v3),
and Alexander Lipton and Marcos Lopez de Prado,
["A Closed-Form Solution for Optimal Mean-Reverting Trading Strategies"](https://arxiv.org/abs/2003.10502v1).
Those model-based results do not establish performance for the proposed NSE
equity strategy. The accompanying literature review supplies the wider evidence
and comparison with existing approaches.

Do not add restricted market data, course documents, contact details, access
tokens or sharing links to this repository. See [data handling](data/README.md).
