"""Replay the frozen development pilot using private, audited SQLite prices.

Run under run_limited.py. Outputs are conditional on explicitly assumed timestamp
semantics and independent session funding. This is not final holdout evidence or
a continuously funded wealth simulation. No raw prices enter public summaries.
"""

import argparse
from collections import Counter
from dataclasses import asdict
from datetime import date, datetime, time, timedelta
import hashlib
import csv
import json
from math import fsum
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from path_robust.engine import Execution, Path as PricePath, Policy
from path_robust.research import ResearchConfig, ResearchState
from path_robust.vendor import VendorRow


CONTRASTS = (("combined_minus_time", Policy.COMBINED.value, Policy.TIME.value),
             ("stop_minus_time", Policy.STOP.value, Policy.TIME.value),
             ("combined_minus_stop", Policy.COMBINED.value, Policy.STOP.value))


def hash_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while block := source.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def calendar_sessions(spec):
    holidays = {date.fromisoformat(day) for day in spec["holidays"]}
    day, last = date.fromisoformat(spec["start_date"]), date.fromisoformat(spec["end_date"])
    output = []
    while day <= last:
        if day.weekday() < 5 and day not in holidays:
            output.append(day)
        day += timedelta(days=1)
    return output


def verify_inputs(connection, audit, config_path):
    """Verify frozen config and stream the database rows against ingestion hashes."""
    protocol_hash = hash_file(config_path)
    if protocol_hash != audit["protocol_sha256"]:
        raise ValueError("frozen protocol hash differs from the input audit; do not silently change settings")
    expected_total = 0
    for source_id, source in enumerate(audit["input_files"], start=1):
        digest, count, first, last = hashlib.sha256(), 0, None, None
        for row in connection.execute(
                "SELECT symbol,stamp,o,h,l,c,volume FROM bars WHERE source_id=? ORDER BY stamp", (source_id,)):
            symbol, stamp, opening, high, low, closing, volume = row
            if symbol != source["symbol"]:
                raise ValueError("database source symbol differs from audit")
            digest.update(f"{symbol},{stamp},{opening!r},{high!r},{low!r},{closing!r},{volume!r}\n".encode())
            count += 1
            first = first or stamp
            last = stamp
        if (count != source["rows"] or first != source["first_label"] or last != source["last_label"]
                or digest.hexdigest() != source["parsed_ohlcv_sha256"]):
            raise ValueError(f"database source {source_id} differs from the audited rows")
        expected_total += count
    if connection.execute("SELECT COUNT(*) FROM bars").fetchone()[0] != expected_total:
        raise ValueError("database contains rows outside the audited sources")
    return {"protocol_sha256": protocol_hash, "input_files": len(audit["input_files"]),
            "input_rows": expected_total, "all_source_row_hashes_verified": True}


def load_session(connection, symbol, day, label, opening, closing):
    """Read one instrument/day; convert assumed labels before session filtering."""
    lower = day.isoformat() + "T00:00:00"
    upper = (day + timedelta(days=1)).isoformat() + "T00:00:00"
    output = []
    for stamp, op, hi, lo, cl, volume in connection.execute(
            "SELECT stamp,o,h,l,c,volume FROM bars WHERE symbol=? AND stamp>=? AND stamp<? ORDER BY stamp",
            (symbol, lower, upper)):
        row = VendorRow(symbol, datetime.fromisoformat(stamp), op, hi, lo, cl, volume)
        bar = row.as_bar(label)
        if bar.timestamp.date() == day and opening <= bar.timestamp.time() < closing:
            output.append(bar)
    return output


def research_config(spec, setting):
    return ResearchConfig(
        universe=tuple(spec["universe"]), index_symbol=spec["index_symbol"],
        starting_capital=spec["reference_capital_inr"], allocation_fraction=spec["allocation_fraction"],
        lookback_sessions=spec["prior_sessions"], signal_window_minutes=spec["signal_window_minutes"],
        first_decision_minutes_after_open=spec["decision_minutes_after_open"],
        decision_interval_minutes=spec["decision_interval_minutes"],
        entry_delay_minutes=setting["delay_minutes"], holding_minutes=spec["holding_minutes"],
        entry_z_threshold=spec["z_threshold"],
        execution=Execution(setting["cost_bp"], setting["stop_slippage_bp"]))


def day_record(result, role):
    ambiguous = {r.episode_id for r in result.executions if r.exit_order_ambiguous}
    unresolved = {r.episode_id for r in result.executions if r.status != "RESOLVED"}
    return {
        "date": result.session_date.isoformat(), "role": role, "status": result.status,
        "candidate_counts": dict(Counter(c.status for c in result.candidates)),
        "planned_episodes": len(result.episodes), "ambiguous_episodes": len(ambiguous),
        "unresolved_episodes": len(unresolved), "issues": list(result.issues),
        "episode_entries": [(e.episode_id, e.entry_at.isoformat(), e.expiry_at.isoformat()) for e in result.episodes],
        "accounts": [{"policy": s.policy, "path": s.path, "net_pnl_inr": s.net_pnl,
                      "net_daily_return_bp": None if s.return_on_reference_capital is None
                      else s.return_on_reference_capital * 10_000,
                      "closing_cash": s.closing_cash, "minimum_available_cash": s.minimum_available_cash}
                     for s in result.scenarios],
    }


def mean_or_none(values):
    return fsum(values) / len(values) if values else None


def account_value(record, policy, path):
    return next(a["net_daily_return_bp"] for a in record["accounts"]
                if a["policy"] == policy and a["path"] == path)


def aggregate_run(records):
    """One common evaluable-day set, with zero-trade days retained if eligible."""
    evaluable = [r for r in records if r["role"] == "evaluation" and r["status"] == "EVALUABLE"]
    means, contrasts = [], []
    for path in PricePath:
        for policy in Policy:
            values = [account_value(r, policy.value, path.value) for r in evaluable]
            if any(value is None for value in values):
                raise ValueError("an evaluable day has a missing scenario value")
            means.append({"policy": policy.value, "path": path.value, "common_days": len(evaluable),
                          "mean_net_daily_return_bp": mean_or_none(values)})
        for name, left, right in CONTRASTS:
            differences = [account_value(r, left, path.value) - account_value(r, right, path.value)
                           for r in evaluable]
            contrasts.append({"contrast": name, "path": path.value, "common_days": len(evaluable),
                              "mean_paired_difference_bp": mean_or_none(differences)})
    counts = Counter()
    for record in records:
        if record["role"] == "evaluation":
            counts.update(record["candidate_counts"])
    diagnostics = {
        "calendar_sessions": len(records),
        "role_counts": dict(Counter(r["role"] for r in records)),
        "evaluation_status_counts": dict(Counter(r["status"] for r in records if r["role"] == "evaluation")),
        "evaluation_candidate_counts": dict(sorted(counts.items())),
        "common_evaluable_days": len(evaluable),
        "evaluable_zero_trade_days": sum(r["planned_episodes"] == 0 for r in evaluable),
        "evaluable_dates": [r["date"] for r in evaluable],
        "planned_unique_episodes_all_evaluation_days": sum(r["planned_episodes"] for r in records if r["role"] == "evaluation"),
        "planned_unique_episodes_evaluable_days": sum(r["planned_episodes"] for r in evaluable),
        "ambiguous_unique_episodes_all_evaluation_days": sum(r["ambiguous_episodes"] for r in records if r["role"] == "evaluation"),
        "ambiguous_unique_episodes_evaluable_days": sum(r["ambiguous_episodes"] for r in evaluable),
        "unresolved_unique_episodes_all_evaluation_days": sum(r["unresolved_episodes"] for r in records if r["role"] == "evaluation"),
        "minimum_available_cash_on_evaluable_days": min(
            (a["minimum_available_cash"] for r in evaluable for a in r["accounts"]), default=None),
    }
    return diagnostics, means, contrasts


def compare_settings(reference, variant):
    left = {r["date"]: r for r in reference if r["role"] == "evaluation" and r["status"] == "EVALUABLE"}
    right = {r["date"]: r for r in variant if r["role"] == "evaluation" and r["status"] == "EVALUABLE"}
    common = sorted(left.keys() & right.keys())
    matched_entries = all(left[d]["episode_entries"] == right[d]["episode_entries"] for d in common)
    rows = []
    for path in PricePath:
        for policy in Policy:
            values = [account_value(right[d], policy.value, path.value)
                      - account_value(left[d], policy.value, path.value) for d in common]
            rows.append({"policy": policy.value, "path": path.value, "intersection_days": len(common),
                         "identical_entries_on_intersection": matched_entries,
                         "mean_variant_minus_reference_bp": mean_or_none(values)})
    return rows


def write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as target:
        if rows:
            writer = csv.DictWriter(target, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "config/m4_pilot.json")
    parser.add_argument("--work-dir", type=Path, default=ROOT / "data/m4_pilot")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "results/m4_pilot")
    args = parser.parse_args()
    spec = json.loads(args.config.read_text(encoding="utf-8"))
    audit_path = args.work_dir / "input_audit.json"
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    database = args.work_dir / "pilot.sqlite"
    connection = sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)
    connection.execute("PRAGMA cache_size=-2048")
    connection.execute("PRAGMA temp_store=FILE")
    try:
        verification = verify_inputs(connection, audit, args.config)
        print(json.dumps({"input_verification": verification}), flush=True)
        sessions = calendar_sessions(spec)
        excluded = set(spec["excluded_nonstandard_sessions"])
        if not excluded <= {day.isoformat() for day in sessions}:
            raise ValueError("excluded session is not on the declared calendar")
        if spec["warmup_sessions"] != spec["prior_sessions"]:
            raise ValueError("pilot warmup must preserve the declared prior-session window")
        opening, closing = time.fromisoformat(spec["normal_session_open"]), time.fromisoformat(spec["normal_session_close"])
        public_means, public_contrasts, public_diagnostics, sensitivity = [], [], [], []
        run_summaries, records_by_run, daily_accounts = [], {}, []
        with (args.work_dir / "replay_ledgers.jsonl").open("w", encoding="utf-8") as ledger:
            for label in spec["timestamp_assumptions"]:
                states = {s["name"]: ResearchState(research_config(spec, s)) for s in spec["scenario_settings"]}
                records = {s["name"]: [] for s in spec["scenario_settings"]}
                for session_index, day in enumerate(sessions):
                    excluded_day = day.isoformat() in excluded
                    role = "excluded_nonstandard" if excluded_day else (
                        "warmup" if session_index < spec["warmup_sessions"] else "evaluation")
                    if excluded_day:
                        stocks, index = {}, []
                    else:
                        stocks = {symbol: load_session(connection, symbol, day, label, opening, closing)
                                  for symbol in spec["universe"]}
                        index = load_session(connection, spec["index_symbol"], day, label, opening, closing)
                    for setting in spec["scenario_settings"]:
                        name = setting["name"]
                        result = states[name].process_day(day, stocks, index, session_open=opening,
                                                          session_close=closing, evaluate=role == "evaluation")
                        record = day_record(result, role)
                        records[name].append(record)
                        ledger.write(json.dumps({"timestamp_assumption": label, "setting": name,
                                                 "role": role, "result": asdict(result)},
                                                default=lambda value: value.isoformat(), allow_nan=False) + "\n")
                        for account in record["accounts"]:
                            daily_accounts.append({"timestamp_assumption": label, "setting": name,
                                                   "date": record["date"], "role": role,
                                                   "status": result.status, **account})
                for setting in spec["scenario_settings"]:
                    name = setting["name"]
                    key = {"timestamp_assumption": label, "setting": name}
                    diagnostics, means, contrasts = aggregate_run(records[name])
                    run_summaries.append({**key, "execution_settings": setting, "diagnostics": diagnostics,
                                          "scenario_means": means, "paired_contrasts": contrasts})
                    public_means.extend({**key, **row} for row in means)
                    public_contrasts.extend({**key, **row} for row in contrasts)
                    public_diagnostics.append({**key, **{k: json.dumps(v, sort_keys=True) if isinstance(v, (dict, list)) else v
                                                         for k, v in diagnostics.items()}})
                    records_by_run[(label, name)] = records[name]
                    if name != "reference":
                        sensitivity.extend({**key, "comparison": "variant_minus_reference_on_common_days", **row}
                                           for row in compare_settings(records["reference"], records[name]))
                    print(json.dumps({**key, "days": diagnostics["common_evaluable_days"],
                                      "episodes": diagnostics["planned_unique_episodes_evaluable_days"],
                                      "ambiguous_episodes": diagnostics["ambiguous_unique_episodes_evaluable_days"]}), flush=True)
        # Timing interpretations may change both signals and entries; compare only
        # their shared evaluable dates and do not call this an isolated fill effect.
        if set(spec["timestamp_assumptions"]) == {"start", "end"}:
            for setting in spec["scenario_settings"]:
                sensitivity.extend({"timestamp_assumption": "end_minus_start", "setting": setting["name"],
                                    "comparison": "timestamp_assumptions_on_common_days", **row}
                                   for row in compare_settings(records_by_run[("start", setting["name"])],
                                                               records_by_run[("end", setting["name"])]))
        args.output_dir.mkdir(parents=True, exist_ok=True)
        write_csv(args.work_dir / "daily_accounts.csv", daily_accounts)
        write_csv(args.output_dir / "scenario_means.csv", public_means)
        write_csv(args.output_dir / "paired_contrasts.csv", public_contrasts)
        write_csv(args.output_dir / "run_diagnostics.csv", public_diagnostics)
        write_csv(args.output_dir / "sensitivity_comparisons.csv", sensitivity)
        summary = {
            "protocol_id": spec["protocol_id"], **verification,
            "input_audit_sha256": hash_file(audit_path), "private_database_sha256": hash_file(database),
            "evidence_label": "INSTRUCTOR MARKET DATA; CONDITIONAL DEVELOPMENT REPLAY; NOT FINAL HOLDOUT",
            "capital_model": spec["capital_model"], "reference_capital_inr": spec["reference_capital_inr"],
            "universe": spec["universe"], "calendar_session_count": len(sessions),
            "warmup_dates": [d.isoformat() for d in sessions[:spec["warmup_sessions"]]],
            "excluded_nonstandard_sessions": sorted(excluded),
            "runs": run_summaries,
            "interpretation_limits": [
                "Minute-start/minute-end labels and IST are assumptions, not supplier-confirmed facts.",
                "Per-day independent K accounts; no continuously funded wealth, compounding or cumulative drawdown claim.",
                "Three submitted policies share entries and the same common six-scenario evaluable-day mask within each run.",
                "Excluded 24 February remains an empty history session, so subsequent incomplete 20-session windows are ineligible.",
                "Ambiguity and episode counts are unique within each run and are not multiplied by six execution scenarios.",
                "Cost/slippage comparisons use the intersection of evaluable dates; delays and timestamp assumptions can change entries.",
                "The 15 bp reference and stress costs are declared scenarios, not reconstructed historical transaction fees.",
                "Five predeclared named examples are not a representative or historically constituent-selected universe.",
                "No final holdout, parameter search, empirical ES/CI/Sharpe or drawdown result is reported in this short pilot.",
            ],
        }
        (args.output_dir / "summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        print(json.dumps({"completed_runs": len(run_summaries), "public_output": str(args.output_dir)}), flush=True)
    finally:
        connection.close()


if __name__ == "__main__":
    main()
