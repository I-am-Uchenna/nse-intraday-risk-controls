# M7 results narrative

`RESULTS.md` is the results note for the pending M7 report. The first paragraph states the cost finding from the saved gross/net table. The Limitations section holds the sample, cost, inference and final-partition qualifications.

The note is generated from recorded development and validation aggregates and from the 11 November 2026 validation reproduction. It does not read market prices, and it stops if a net mean is no longer negative or if the reproduction record says the final partition was evaluated.

```bash
python scripts/m7_results_narrative.py
```

Run that from a checkout where `path_robust` imports (`pip install -r requirements.txt`). The command rewrites `RESULTS.md`.
