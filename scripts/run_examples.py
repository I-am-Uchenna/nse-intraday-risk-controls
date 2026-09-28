"""Generate deterministic synthetic execution examples, never market findings."""

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from path_robust.engine import Path as PricePath, paired_difference_bp, simulate_policies
from path_robust.fixtures import LABEL, cases


def csv_file(path, rows):
    with path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def number(value):
    return "UNRESOLVED" if value is None else f"{value:+.6f}"


def main():
    output = ROOT / "results"
    output.mkdir(exist_ok=True)
    fixture_rows, episode_rows, ledger, comparisons = [], [], [], []
    case_notes = {}
    for case in cases():
        case_notes[case.name] = case.purpose
        episode_rows.append({
            "data_label": LABEL, "case": case.name, "purpose": case.purpose,
            "signal_at": case.episode.signal_at.isoformat(),
            "entry_at": case.episode.entry_at.isoformat(),
            "expiry_at": case.episode.expiry_at.isoformat(),
            "stop_multiplier": case.episode.stop_multiplier,
            "target_multiplier": case.episode.target_multiplier,
            "entry_notional": case.episode.entry_notional,
            "round_trip_cost_bp": case.execution.round_trip_cost_bp,
            "extra_stop_slippage_bp": case.execution.extra_stop_slippage_bp,
        })
        for bar in case.bars:
            fixture_rows.append({"data_label": LABEL, "case": case.name,
                                 "symbol": bar.symbol, "timestamp": bar.timestamp.isoformat(),
                                 "open": bar.open, "high": bar.high,
                                 "low": bar.low, "close": bar.close})
        for path in PricePath:
            time, stop, combined = simulate_policies(case.bars, case.episode, path, case.execution)
            for result in (time, stop, combined):
                ledger.append({"data_label": LABEL, "case": case.name, **result.to_record()})
            all_resolved = all(result.status == "RESOLVED" for result in (time, stop, combined))
            comparisons.append({
                "data_label": LABEL, "case": case.name, "path": path.value,
                "all_three_resolved": all_resolved,
                "time_only_net_bp": time.net_return_bp,
                "stop_only_net_bp": stop.net_return_bp,
                "combined_net_bp": combined.net_return_bp,
                "combined_minus_time_bp": paired_difference_bp(combined, time)
                if time.status == combined.status == "RESOLVED" else None,
                "stop_minus_time_bp": paired_difference_bp(stop, time)
                if time.status == stop.status == "RESOLVED" else None,
                "combined_minus_stop_bp": paired_difference_bp(combined, stop)
                if stop.status == combined.status == "RESOLVED" else None,
            })
    csv_file(ROOT / "examples" / "synthetic_bars.csv", fixture_rows)
    (ROOT / "examples" / "synthetic_episodes.json").write_text(
        json.dumps(episode_rows, indent=2) + "\n", encoding="utf-8")
    csv_file(output / "synthetic_examples.csv", ledger)
    csv_file(output / "synthetic_comparisons.csv", comparisons)
    summary = {
        "data_label": LABEL,
        "scope": "Deterministic execution illustrations, not empirical performance estimates.",
        "case_count": len(case_notes), "policy_results": len(ledger),
        "resolved_results": sum(row["status"] == "RESOLVED" for row in ledger),
        "unresolved_results": sum(row["status"] == "UNRESOLVED" for row in ledger),
        "case_notes": case_notes, "comparisons": comparisons,
    }
    (output / "synthetic_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    lines = ["# Initial execution checks", "", f"**{LABEL}.**", "",
             "These hand-constructed prices test declared execution rules. They do not establish",
             "profitability, a market effect, a confidence interval, or expected strategy risk.", "",
             "The main fixture enters at 100, stops at 99, targets 101 and expires 15 minutes",
             "later at an opening price of 100.5. Its entry candle has low 98.5 and high 101.5.",
             "Round-trip costs are 15 bp of entry notional unless a case states otherwise.", "",
             "| Example | Assumed path | Time-only net bp | Stop-only net bp | Combined net bp | Combined minus time bp |",
             "| --- | --- | ---: | ---: | ---: | ---: |"]
    for row in comparisons:
        lines.append(f"| {row['case']} | {row['path']} | {number(row['time_only_net_bp'])} | "
                     f"{number(row['stop_only_net_bp'])} | {number(row['combined_net_bp'])} | "
                     f"{number(row['combined_minus_time_bp'])} |")
    lines += ["", "In the both-hit fixture, combined-minus-time changes from -150 bp under",
              "O-L-H-C to +50 bp under O-H-L-C. The ordering assumption changes the ranking",
              "while the observed OHLC is identical. This is a demonstration, not a measured",
              "frequency or effect in NSE data.", "",
              "Increasing identical costs from 15 to 25 bp reduces each completed return by",
              "10 bp and leaves matched differences unchanged. An extra 10 bp on stop exits",
              "changes only the outcomes that actually exit at a stop.", "",
              "UNRESOLVED is stored as null in JSON and a blank numeric cell in CSV, never",
              "as a zero. An already closed policy can be resolved while its time-only",
              "benchmark fails the strict active-period coverage rule. Its paired difference",
              "is then withheld. Time-only endpoint P&L may still be arithmetically known",
              "when only interior bars are absent; withholding it is a declared data-quality",
              "rule, not a statement that endpoint arithmetic is impossible.", "",
              "The two paths are coherent scenarios and do not reconstruct actual tick order",
              "or bound portfolio drawdown. Touch fills remain assumptions.", "",
              "## Next empirical step", "",
              "Audit the supplied market data, map its timestamps and instruments, and implement",
              "past-only signals and portfolio accounting before any market performance study.", ""]
    (output / "initial_findings.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"{LABEL}: {len(case_notes)} cases, {len(ledger)} policy/path outcomes; "
          f"{summary['resolved_results']} resolved, {summary['unresolved_results']} unresolved.")
    print("Both-hit combined-minus-time: -150 bp (O-L-H-C); +50 bp (O-H-L-C).")
    print(f"Results written to {output}")


if __name__ == "__main__":
    main()
