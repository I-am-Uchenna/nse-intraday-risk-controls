"""Derive peer-review tables from saved aggregates; never replay prices or final data."""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path


def peer_review_tables(stage, means, episodes, es, statuses, split, sensitivity,
                       capital=100000.0, allocation=.5, stock_count=5, cost_bp=15.0):
    """Keep stages separate; recover gross returns only for the matched fixed-fee model."""
    if stage not in {"pilot", "development", "validation"}:
        raise ValueError("Final-stage outcomes are not permitted")
    if not (capital > 0 and 0 < allocation <= 1 and stock_count > 0 and cost_bp == 15):
        raise ValueError("Positive capital/allocation and the declared 15 bp reference are required")

    def one(rows, **keys):
        matches = [r for r in rows if all(r.get(k) == v for k, v in keys.items())]
        if len(matches) != 1:
            raise ValueError(f"Expected one row for {keys}; found {len(matches)}")
        return matches[0]

    def equal(a, b):
        if not math.isclose(a, b, rel_tol=0, abs_tol=1e-8):
            raise ValueError(f"Inconsistent matched aggregates: {a} != {b}")

    gross, samples, tails = [], [], []
    fraction = allocation / stock_count
    scheduled = int(one(split, stage=stage)["scheduled_sessions"])
    for label in ("start", "end"):
        count = int(one(episodes, timestamp_label=label)["unique_episodes"])
        if count < 0:
            raise ValueError("Episode count cannot be negative")
        ref_status = [r for r in statuses if r["timestamp_label"] == label and r["setting"] == "reference"]
        primary = [r for r in ref_status if r["accounting"] == "independent"]
        equal(sum(int(r["scheduled_days"]) for r in primary), scheduled)
        eligible = int(one(primary, status="EVALUABLE")["scheduled_days"])
        if eligible <= 0:
            raise ValueError("No primary evaluable days; do not report a gross average")
        funded = sum(int(r["scheduled_days"]) for r in ref_status
                     if r["accounting"] == "funded" and r["status"] == "EVALUABLE")
        samples.append(dict(stage=stage, timestamp_label=label, scheduled_days=scheduled,
            primary_evaluable_days=eligible, primary_unavailable_days=scheduled-eligible,
            explicitly_excluded_days=sum(int(r["scheduled_days"]) for r in primary
                                         if r["status"] == "EXCLUDED_SESSION"),
            incomplete_candidate_days=sum(int(r["scheduled_days"]) for r in primary
                                         if r["status"] == "INCOMPLETE_CANDIDATE_COVERAGE"),
            funded_identified_days=funded, reference_unique_episodes=count,
            mean_episodes_per_primary_day=count/eligible))
        for policy in ("time_only", "stop_only", "stop_and_target"):
            keys = dict(timestamp_label=label, policy=policy, path="O-L-H-C")
            rows = {s: one(means, setting=s, **keys) for s in ("reference", "cost_5", "cost_25")}
            for row in rows.values():
                equal(float(row["evaluable_days"]), eligible)
            net = float(rows["reference"]["mean_daily_pnl_bp"])
            fee = cost_bp * fraction * count / eligible
            # Independent arithmetic check: a 20 bp fee change across identical entries.
            fee_slope = (float(rows["cost_5"]["mean_daily_pnl_bp"])
                         - float(rows["cost_25"]["mean_daily_pnl_bp"])) / 20
            equal(fee_slope, fraction*count/eligible)
            gross_daily = net + fee
            gross.append(dict(stage=stage, timestamp_label=label, policy=policy,
                primary_days=eligible, unique_episodes=count, entry_fraction_of_capital=fraction,
                net_bp_per_day=net, fee_bp_per_day=fee, gross_bp_per_day=gross_daily,
                gross_bp_per_trade=gross_daily*eligible/(fraction*count) if count else None,
                net_inr_per_day=net*capital/10000, gross_inr_per_day=gross_daily*capital/10000,
                reference_round_trip_fee_bp=cost_bp))
            tail = one(es, **keys)
            equal(float(tail["n_days"]), eligible)
            equal(float(tail["tail_mass_days"]), .025*eligible)
            tails.append(dict(stage=stage, **{k: tail[k] for k in (
                "timestamp_label", "policy", "n_days", "tail_mass_days", "ES975_loss_bp",
                "leave_one_day_out_min_bp", "leave_one_day_out_max_bp")}))
    aligned = [dict(stage=stage, **row) for row in sensitivity]
    for row in aligned:
        equal(float(row["scenario_difference_bp"])-float(row["reference_difference_bp"]),
              float(row["change_from_reference_bp"]))
        n = int(float(row["aligned_days"]))
        if n <= 0 or n > scheduled:
            raise ValueError("Invalid aligned sample size")
    return {"gross_net_returns": gross, "sample_accounting": samples,
            "expected_shortfall_sensitivity": tails, "execution_sensitivity": aligned}


def derive(development, validation, output):
    sources = [("development", Path(development)), ("validation", Path(validation))]
    output = Path(output).resolve()
    if output.exists() or any(output.is_relative_to(p.resolve()) for _, p in sources):
        raise FileExistsError("Choose a new output folder outside both recorded runs")
    combined, provenance = {}, []
    for stage, folder in sources:
        manifest_data = (folder/"run_manifest.json").read_bytes()
        manifest = json.loads(manifest_data)
        if manifest.get("stage") != stage:
            raise ValueError("Stage mismatch; final results must not be read")
        hashes = {"run_manifest.json": hashlib.sha256(manifest_data).hexdigest()}
        records = []
        for name in ("policy_means", "exit_ambiguity", "expected_shortfall", "status_counts",
                     "calendar_split", "aligned_sensitivity"):
            data = (folder/f"{name}.csv").read_bytes()
            hashes[f"{name}.csv"] = hashlib.sha256(data).hexdigest()
            records.append(list(csv.DictReader(data.decode("utf-8-sig").splitlines())))
        cfg = manifest["science"]["configuration"]
        tables = peer_review_tables(stage, *records, capital=cfg["reference_capital_inr"],
            allocation=cfg["allocation_fraction"], stock_count=len(cfg["universe"]))
        for name, rows in tables.items():
            combined.setdefault(name, []).extend(rows)
        provenance.append(dict(stage=stage, run_id=manifest["run_id"], source_sha256=hashes))
    output.mkdir(parents=True)
    for name, rows in combined.items():
        with (output/f"{name}.csv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader(); writer.writerows(rows)
    notes = [
        "Post-review arithmetic from recorded development/validation aggregates; no raw prices or final outcomes read.",
        "Gross returns add back the declared identical fixed-notional fees; they are not random-entry-adjusted alpha.",
        "Per-trade means use equal entry notionals; bp/day and INR/day use fixed initial capital, not compounded wealth.",
        "Sample counts distinguish primary complete cases from funded identified days; counts alone cannot locate the causes of individual exclusions.",
        "All scenarios and risk ranges are descriptive. Leave-one-day-out ranges are not confidence intervals or a common-date policy ranking.",
        "Final dates in the calendar are schedule metadata, not final strategy outcomes. No samples are pooled."]
    (output/"provenance.json").write_text(json.dumps(dict(sources=provenance, notes=notes),
        indent=2, allow_nan=False)+"\n", encoding="utf-8")
    (output/"SHA256SUMS.txt").write_text("".join(
        hashlib.sha256(p.read_bytes()).hexdigest()+"  "+p.name+"\n"
        for p in sorted(output.iterdir()) if p.is_file()), encoding="utf-8")
    return combined


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("development", "validation", "output"):
        parser.add_argument(f"--{name}", required=True, type=Path)
    args = parser.parse_args()
    tables = derive(args.development, args.validation, args.output)
    print({name: len(rows) for name, rows in tables.items()})
