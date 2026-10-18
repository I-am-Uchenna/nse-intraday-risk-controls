"""Build report tables from saved development/validation aggregates, never market data.

Run: python scripts/summarize_m6.py --development results/development_20261001 \
     --validation PATH_TO_VALIDATION_OUTPUTS --output PATH_TO_NEW_SUMMARY
All estimates retain their original stage; no samples or funded segments are pooled.
"""

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

POLICIES = ("time_only", "stop_only", "stop_and_target")
CONTRASTS = {"combined_minus_time": ("stop_and_target", "time_only"),
             "stop_minus_time": ("stop_only", "time_only"),
             "combined_minus_stop": ("stop_and_target", "stop_only")}
SETTINGS = ("reference", "cost_5", "cost_25", "stop_slippage_5",
            "stop_slippage_10", "delay_2", "delay_5")
PATH = "O-L-H-C"


def number(row, key):
    value = float(row[key])
    if not math.isfinite(value):
        raise ValueError(f"Missing/nonfinite {key}: {row}")
    return value


def equal(actual, expected, description):
    if not math.isclose(actual, expected, rel_tol=0, abs_tol=1e-9):
        raise ValueError(f"{description}: {actual} != {expected}")


def one(rows, **key):
    matches = [r for r in rows if all(r.get(k) == v for k, v in key.items())]
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one row for {key}; found {len(matches)}")
    return matches[0]


def read_stage(folder, stage):
    """Validate identities first so final-stage result CSVs are never opened."""
    folder = Path(folder)
    manifest_bytes = (folder / "run_manifest.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    if stage not in ("development", "validation") or manifest.get("stage") != stage:
        raise ValueError(f"Expected {stage} manifest; final-stage summaries are not allowed")
    hashes = {"run_manifest.json": hashlib.sha256(manifest_bytes).hexdigest()}

    def read(name):
        data = (folder / f"{name}.csv").read_bytes()
        hashes[f"{name}.csv"] = hashlib.sha256(data).hexdigest()
        return list(csv.DictReader(data.decode("utf-8-sig").splitlines()))

    means, effects, es, ambiguity, funded, sensitivity = [read(name) for name in (
        "policy_means", "paired_effects", "expected_shortfall", "exit_ambiguity",
        "funded_drawdown", "aligned_sensitivity")]
    reference, paired, ambiguities = [], [], []
    for label in ("start", "end"):
        policy_rows = {p: one(means, timestamp_label=label, setting="reference",
                              path=PATH, policy=p) for p in POLICIES}
        n = number(policy_rows["time_only"], "evaluable_days")
        if n <= 0 or not n.is_integer():
            raise ValueError(f"{stage}/{label}: positive integer evaluable days required")
        for contrast, (left, right) in CONTRASTS.items():
            row = one(effects, timestamp_label=label, setting="reference",
                      path=PATH, contrast=contrast)
            equal(number(row, "n_days"), n, "Paired sample size")
            difference = number(row, "mean_difference_bp")
            equal(difference, number(policy_rows[left], "mean_daily_pnl_bp") -
                  number(policy_rows[right], "mean_daily_pnl_bp"), contrast)
            paired.append(dict(stage=stage, timestamp_label=label, contrast=contrast,
                               n_days=int(n), mean_difference_bp=difference))
        for policy, row in policy_rows.items():
            tail = one(es, timestamp_label=label, path=PATH, policy=policy)
            equal(number(row, "evaluable_days"), n, "Common policy sample")
            equal(number(tail, "n_days"), n, "ES sample size")
            equal(number(tail, "tail_mass_days"), .025 * n, "ES97.5 tail mass")
            mean = number(row, "mean_daily_pnl_bp")
            reference.append(dict(stage=stage, timestamp_label=label, policy=policy,
                n_days=int(n), mean_daily_pnl_bp=mean,
                policy_minus_time_bp=mean - number(policy_rows["time_only"], "mean_daily_pnl_bp"),
                ES975_loss_bp=number(tail, "ES975_loss_bp"),
                tail_mass_days=number(tail, "tail_mass_days")))
        row = one(ambiguity, timestamp_label=label)
        eligible, ambiguous = number(row, "unique_episodes"), number(row, "ambiguous_episodes")
        if not (eligible.is_integer() and ambiguous.is_integer() and 0 <= ambiguous <= eligible):
            raise ValueError(f"Invalid ambiguity counts: {row}")
        rate = number(row, "ambiguity_rate") if eligible else None
        if eligible:
            equal(rate, ambiguous / eligible, "Ambiguity rate")
        ambiguities.append(dict(stage=stage, timestamp_label=label,
            unique_episodes=int(eligible), ambiguous_episodes=int(ambiguous), ambiguity_rate=rate))

    # Preserve every funded segment and both valuation frequencies, without joining paths.
    funded_rows = []
    keys = set()
    for row in funded:
        if row["path"] != PATH:
            continue
        key = (row["timestamp_label"], row["segment"], row["policy"])
        if key in keys:
            raise ValueError(f"Duplicate funded segment: {key}")
        keys.add(key)
        converted = dict(row, stage=stage)
        for field in ("max_drawdown_pct", "saved_marks", "daily_close_max_drawdown_pct",
                      "identified_daily_closes", "segment_initial_capital"):
            # A segment interrupted before a daily close legitimately has no daily drawdown.
            converted[field] = number(row, field) if row[field] else None
        funded_rows.append(converted)

    # Aligned sensitivity uses each row's own common dates, not an invented pooled sample.
    sensitivity_rows = []
    for label in ("start", "end"):
        for setting in SETTINGS:
            for contrast in CONTRASTS:
                row = one(sensitivity, timestamp_label=label, setting=setting, contrast=contrast)
                converted = dict(row, stage=stage)
                for field in ("aligned_days", "reference_difference_bp",
                              "scenario_difference_bp", "change_from_reference_bp"):
                    converted[field] = number(row, field)
                equal(converted["change_from_reference_bp"],
                      converted["scenario_difference_bp"] - converted["reference_difference_bp"],
                      "Aligned sensitivity change")
                if setting == "reference":
                    effect = one(paired, timestamp_label=label, contrast=contrast)
                    equal(converted["aligned_days"], effect["n_days"], "Reference aligned sample")
                    equal(converted["scenario_difference_bp"], effect["mean_difference_bp"],
                          "Reference aligned effect")
                sensitivity_rows.append(converted)
    science = manifest.get("science", {})
    return dict(stage=stage, run_id=manifest["run_id"],
        protocol_sha256=manifest.get("protocol_sha256"), source_sha256=hashes,
        evaluation_window=next((r for r in science.get("splits", []) if r["stage"] == stage), None),
        reference_execution=next((r for r in science.get("settings", []) if r["name"] == "reference"), None),
        configuration=science.get("configuration"),
        parsed_data_sha256=science.get("parsed_data_sha256"),
        raw_inputs_reverified=manifest.get("raw_inputs_reverified"),
        independent_economic_failure=manifest.get("independent_economic_failure"),
        reference=reference, paired_effects=paired, ambiguity=ambiguities,
        funded_drawdown=funded_rows, sensitivity=sensitivity_rows)


def summarize(development, validation, output):
    output = Path(output).resolve()
    if any(output.is_relative_to(Path(p).resolve()) for p in (development, validation)):
        raise ValueError("Output must be outside both source folders")
    names = ("comparison.csv", "sensitivity.csv", "summary.json")
    if any((output / name).exists() for name in names):
        raise FileExistsError("Use a new output directory; existing summaries are not overwritten")
    stages = [read_stage(development, "development"), read_stage(validation, "validation")]
    output.mkdir(parents=True, exist_ok=True)
    for name, key in (("comparison.csv", "reference"), ("sensitivity.csv", "sensitivity")):
        rows = [row for stage in stages for row in stage[key]]
        with (output / name).open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    summary = dict(reference_path=PATH, stages=stages, notes=[
        "Saved aggregates only; no market replay or final-stage evaluation.",
        "Means and ES use common evaluable session-reset accounts; missing days are not zero.",
        "Funded drawdowns retain separate segments and minute/boundary versus daily-close marks.",
        "Funded samples need not equal the primary sample. No funded segments are concatenated.",
        "All inference remains exploratory. ES is descriptive; zero ambiguity does not establish robustness."])
    (output / "summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("development", "validation", "output"):
        parser.add_argument(f"--{name}", required=True, type=Path)
    args = parser.parse_args()
    summarize(args.development, args.validation, args.output)
    print(f"Saved comparison.csv, sensitivity.csv and summary.json to {args.output}")
