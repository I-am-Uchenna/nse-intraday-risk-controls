"""Write the M7 results note from saved aggregates.

The note leads with the cost finding and keeps qualifications in Limitations.
It reads recorded development and validation tables only. It does not open
price files, and it rejects a run whose manifest says the final partition
was evaluated.
"""
import argparse
import csv
import json
import math
import textwrap
from pathlib import Path

STAGES = ("development", "validation")
LABELS = ("start", "end")
POLICIES = ("time_only", "stop_only", "stop_and_target")
PATHS = ("O-L-H-C", "O-H-L-C")
REFERENCE_PATH = "O-L-H-C"
PRIMARY_BLOCK = "5"
CONTRAST = "combined_minus_time"
STAGE_DATES = {
    "development": "1 January 2021–17 October 2022",
    "validation": "18 October 2022–25 May 2023",
}
POLICY_NAME = {
    "time_only": "Time-only",
    "stop_only": "Stop-only",
    "stop_and_target": "Stop and target",
}
NUMERIC_GROSS = (
    "primary_days", "unique_episodes", "entry_fraction_of_capital",
    "net_bp_per_day", "fee_bp_per_day", "gross_bp_per_day",
    "gross_bp_per_trade", "net_inr_per_day", "gross_inr_per_day",
    "reference_round_trip_fee_bp",
)


def read_csv(path):
    return list(csv.DictReader(Path(path).read_text(encoding="utf-8-sig").splitlines()))


def num(row, key):
    value = float(row[key])
    if not math.isfinite(value):
        raise ValueError(f"Non-finite {key}: {row}")
    return value


def bp(value):
    return f"{float(value):.4f}"


def one(rows, description, **keys):
    matches = [r for r in rows if all(str(r.get(k)) == str(v) for k, v in keys.items())]
    if len(matches) != 1:
        raise ValueError(f"Expected one row for {description} {keys}; found {len(matches)}")
    return matches[0]


def paragraph(text):
    return textwrap.fill(" ".join(text.split()), width=100, break_on_hyphens=False)


def _time_only(gross):
    rows = [r for r in gross if r["policy"] == "time_only"]
    if len(rows) != len(STAGES) * len(LABELS):
        raise ValueError("Time-only gross rows must cover both stages and both timestamp labels")
    return rows


def assert_costs_dominate(gross):
    """Gross is net plus the fixed fee, so a negative net is a gross that misses the fee."""
    if len(gross) != len(STAGES) * len(LABELS) * len(POLICIES):
        raise ValueError("Expected twelve development and validation policy rows")
    stages = {r["stage"] for r in gross}
    if stages != set(STAGES):
        raise ValueError(f"Narrative accepts development and validation only; found {sorted(stages)}")
    for row in gross:
        if num(row, "net_bp_per_day") >= 0 or num(row, "gross_bp_per_day") >= num(row, "fee_bp_per_day"):
            raise ValueError(
                "A recorded net mean is not negative, so the losing-money headline would be false: "
                f"{row['stage']} {row['timestamp_label']} {row['policy']}"
            )


def _ranking_holds(shortfalls, drawdowns):
    for stage in STAGES:
        for label in LABELS:
            base_es = num(one(shortfalls, "ES", stage=stage, timestamp_label=label,
                              policy="time_only", path=REFERENCE_PATH), "ES975_loss_bp")
            base_dd = num(one(drawdowns, "drawdown", stage=stage, timestamp_label=label,
                              policy="time_only", path=REFERENCE_PATH, segment="1"),
                          "daily_close_max_drawdown_pct")
            for policy in ("stop_only", "stop_and_target"):
                es = num(one(shortfalls, "ES", stage=stage, timestamp_label=label,
                             policy=policy, path=REFERENCE_PATH), "ES975_loss_bp")
                dd = num(one(drawdowns, "drawdown", stage=stage, timestamp_label=label,
                             policy=policy, path=REFERENCE_PATH, segment="1"),
                         "daily_close_max_drawdown_pct")
                if es >= base_es or dd <= base_dd:
                    raise ValueError(
                        "Stop-based ES and drawdown do not both rank as stated for "
                        f"{stage} {label} {policy}"
                    )


def _contrasts_negative(contrasts):
    found = []
    for stage in STAGES:
        for label in LABELS:
            for path in PATHS:
                row = one(contrasts, "contrast", stage=stage, timestamp_label=label,
                          setting="reference", path=path, contrast=CONTRAST)
                if num(row, "mean_difference_bp") >= 0:
                    raise ValueError(f"Combined minus time-only is not negative for {stage} {label} {path}")
                found.append(row)
    return found


def render_narrative(gross, contrasts, drawdowns, shortfalls, ambiguity, samples, intervals, reproduction):
    """Return the results note. Raises if the saved signs do not support the headline."""
    assert_costs_dominate(gross)
    _ranking_holds(shortfalls, drawdowns)
    _contrasts_negative(contrasts)
    if reproduction.get("final_test_evaluated") is not False:
        raise ValueError("Final-partition outcomes are not part of this narrative")
    if reproduction.get("maximum_numeric_difference") != 0:
        raise ValueError("Validation reproduction did not match exactly")

    entry = _time_only(gross)
    gross_lo = min(num(r, "gross_bp_per_day") for r in entry)
    gross_hi = max(num(r, "gross_bp_per_day") for r in entry)
    fee_lo = min(num(r, "fee_bp_per_day") for r in entry)
    fee_hi = max(num(r, "fee_bp_per_day") for r in entry)
    nets = [num(r, "net_bp_per_day") for r in gross]
    opening = paragraph(
        f"The entry signal earns {bp(gross_lo)}–{bp(gross_hi)} bp of reference capital per evaluable "
        f"day before costs, against assumed fees of {bp(fee_lo)}–{bp(fee_hi)} bp per day. "
        f"The fee exceeds that gross in every recorded cell. Time-only, stop-only and stop-and-target "
        f"are three ways of losing money: every recorded net mean is negative, between {bp(min(nets))} "
        f"and {bp(max(nets))} bp per day."
    )

    order = {(s, lab, p): i for i, (s, lab, p) in enumerate(
        (s, lab, p) for s in STAGES for lab in LABELS for p in POLICIES)}
    table = [
        "| Stage | Label | Exit | Days | Gross bp/day | Fee bp/day | Net bp/day |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for row in sorted(gross, key=lambda r: order[(r["stage"], r["timestamp_label"], r["policy"])]):
        table.append(
            f"| {row['stage'].title()} | {row['timestamp_label']} | {POLICY_NAME[row['policy']]} | "
            f"{int(num(row, 'primary_days'))} | {bp(row['gross_bp_per_day'])} | "
            f"{bp(row['fee_bp_per_day'])} | {bp(row['net_bp_per_day'])} |"
        )

    contrast_bits = []
    for stage in STAGES:
        for label in LABELS:
            row = one(contrasts, "contrast", stage=stage, timestamp_label=label,
                      setting="reference", path=REFERENCE_PATH, contrast=CONTRAST)
            contrast_bits.append(
                f"{stage} {label} labels {bp(row['mean_difference_bp'])} bp/day "
                f"({int(num(row, 'n_days'))} days)"
            )
    example = one(shortfalls, "ES", stage="validation", timestamp_label="start",
                  policy="time_only", path=REFERENCE_PATH)
    stop_es = one(shortfalls, "ES", stage="validation", timestamp_label="start",
                  policy="stop_only", path=REFERENCE_PATH)
    both_es = one(shortfalls, "ES", stage="validation", timestamp_label="start",
                  policy="stop_and_target", path=REFERENCE_PATH)
    example_dd = one(drawdowns, "drawdown", stage="validation", timestamp_label="start",
                     policy="time_only", path=REFERENCE_PATH, segment="1")
    stop_dd = one(drawdowns, "drawdown", stage="validation", timestamp_label="start",
                  policy="stop_only", path=REFERENCE_PATH, segment="1")
    both_dd = one(drawdowns, "drawdown", stage="validation", timestamp_label="start",
                  policy="stop_and_target", path=REFERENCE_PATH, segment="1")
    ambiguity_bits = []
    for stage in STAGES:
        for label in LABELS:
            row = one(ambiguity, "ambiguity", stage=stage, timestamp_label=label)
            episodes = int(num(row, "unique_episodes"))
            sample = one(samples, "sample", stage=stage, timestamp_label=label)
            if int(num(sample, "reference_unique_episodes")) != episodes:
                raise ValueError(f"Ambiguity episode count disagrees with the sample table for {stage} {label}")
            ambiguity_bits.append(
                f"{stage} {label} labels {int(num(row, 'ambiguous_episodes'))} of {episodes}"
            )

    results = [
        paragraph(
            "Gross return in this table is the recorded net return plus the declared 15 bp round-trip "
            "fee on entry notional. The fee uses one tenth of reference capital per episode. "
            "Time-only is the entry held to the common 15-minute cap. Stop-only and stop-and-target "
            "change that exit. The table reports all three."
        ),
        "\n".join(table),
        paragraph(
            "Combined minus time-only, at reference execution, is negative under both candle orderings "
            "in every recorded cell. On open-low-high-close ordering the four estimates are "
            + "; ".join(contrast_bits) + "."
        ),
        paragraph(
            "Both stop-based exits have lower 97.5 percent expected shortfall than time-only, and deeper "
            "daily-close funded drawdown than time-only, in every stage and timestamp label under "
            "open-low-high-close ordering. On the validation start-label accounts the shortfall is "
            f"{bp(example['ES975_loss_bp'])} bp for time-only, {bp(stop_es['ES975_loss_bp'])} bp for "
            f"stop-only and {bp(both_es['ES975_loss_bp'])} bp for stop and target. Daily-close drawdown "
            f"on those accounts is {bp(example_dd['daily_close_max_drawdown_pct'])} percent, "
            f"{bp(stop_dd['daily_close_max_drawdown_pct'])} percent and "
            f"{bp(both_dd['daily_close_max_drawdown_pct'])} percent of starting capital."
        ),
        paragraph(
            "Reference episodes that touch both barriers inside one active candle: "
            + "; ".join(ambiguity_bits) + "."
        ),
        paragraph(
            f"These figures cover development ({STAGE_DATES['development']}) and validation "
            f"({STAGE_DATES['validation']}). Run {reproduction['run_id']} on 11 November 2026 "
            "reproduced the validation gross, fee and net figures. The largest numeric difference "
            "in that comparison is 0."
        ),
    ]

    coverage = []
    for stage in STAGES:
        for label in LABELS:
            row = one(samples, "sample", stage=stage, timestamp_label=label)
            coverage.append(
                f"{stage} {label} labels use {int(num(row, 'primary_evaluable_days'))} of "
                f"{int(num(row, 'scheduled_days'))} scheduled sessions"
            )
    interval_bits = []
    for stage in STAGES:
        for label in LABELS:
            row = one(intervals, "interval", stage=stage, timestamp_label=label,
                      path=REFERENCE_PATH, contrast=CONTRAST, block_length=PRIMARY_BLOCK)
            if not str(row.get("lower_bp", "")).strip():
                raise ValueError(f"Primary interval missing for {stage} {label}")
            interval_bits.append(
                f"{stage} {label} labels [{bp(row['lower_bp'])}, {bp(row['upper_bp'])}]"
            )
    tails = []
    for stage in STAGES:
        for label in LABELS:
            row = one(shortfalls, "ES", stage=stage, timestamp_label=label,
                      policy="time_only", path=REFERENCE_PATH)
            mass = num(row, "tail_mass_days")
            shown = f"{mass:.2f}" if math.isclose(mass, round(mass, 2), abs_tol=1e-9) else f"{mass:.3f}"
            tails.append(f"{stage} {label} labels {shown} days")

    limitations = [
        paragraph(
            "These statements describe the recorded development and validation samples. "
            + ". ".join(s[0].upper() + s[1:] for s in coverage) + ". "
            "Sessions that fail the complete-case rule are omitted. They are not entered as zero returns. "
            "The five stocks were fixed before the recorded outcomes. They are not a random sample of the "
            "exchange, and the two partitions are not pooled."
        ),
        paragraph(
            "The 15 bp round-trip fee is a declared scenario charged on entry notional. It is not a measured "
            "spread, impact or queue. A minute candle does not identify which barrier printed first. "
            "Open-low-high-close and open-high-low-close are two fill scenarios. Counts of candles that touch "
            "both barriers do not recover historical ticks, and they do not establish path robustness beyond "
            "this sample."
        ),
        paragraph(
            "The nominal 95 percent moving-block intervals for combined minus time-only, using five-session "
            "blocks and open-low-high-close ordering, are "
            + "; ".join(interval_bits) + ". "
            "Synthetic diagnostics for this procedure show undercoverage, so the intervals stay exploratory. "
            "An interval that excludes zero is not a confirmed population effect. No economic adoption "
            "threshold was set in advance."
        ),
        paragraph(
            "Expected shortfall uses a thin tail: " + "; ".join(tails) + ". "
            "Leave-one-day-out ranges in the saved tables are sensitivities. They are not confidence intervals, "
            "and they do not show whether the policy ranking survives deletion of one shared worst day. "
            "The public aggregates do not contain the daily series that check would need. Funded drawdown "
            "follows cash and marked positions through time. It is a different account path from the "
            "independent-session mean and from expected shortfall. A lower shortfall beside a deeper "
            "drawdown is two results, not one."
        ),
        paragraph(
            "The final partition, 26 May–29 December 2023, has not been evaluated. "
            f"Run {reproduction['run_id']} records final_test_evaluated as false. "
            "The statements in Results are not an estimate of that partition, of other stocks, or of other "
            "cost schedules."
        ),
    ]
    sources = paragraph(
        "Group 17838, 12 November 2026. Built from results/peer_review_20261022/gross_net_returns.csv, "
        "the development_20261001 and validation_20261018 aggregate tables, and "
        f"results/m7_validation_20261111 (run {reproduction['run_id']}). "
        "No price file is read. Regenerate with python scripts/m7_results_narrative.py."
    )
    parts = [opening, "", "## Results", "", "\n\n".join(results), "",
             "## Limitations", "", "\n\n".join(limitations), "",
             "## Sources", "", sources, ""]
    return "\n".join(parts)


def _tag(rows, stage):
    tagged = []
    for row in rows:
        if row.get("stage") not in (None, "", stage):
            raise ValueError(f"Stage mismatch in {stage} table: {row.get('stage')}")
        tagged.append({**row, "stage": stage})
    return tagged


def _same_number(left, right):
    return math.isclose(float(left), float(right), rel_tol=0, abs_tol=1e-9)


def validation_matches_reproduction(peer_gross, reproduced_gross):
    """Require the 11 November validation gross table to match the peer-review rows."""
    if any(r.get("stage") != "validation" for r in reproduced_gross):
        raise ValueError("The reproduction gross table must contain validation rows only")
    if len(reproduced_gross) != len(LABELS) * len(POLICIES):
        raise ValueError("Expected six reproduced validation rows")
    for label in LABELS:
        for policy in POLICIES:
            recorded = one(peer_gross, "peer gross", stage="validation",
                           timestamp_label=label, policy=policy)
            fresh = one(reproduced_gross, "reproduced gross", stage="validation",
                        timestamp_label=label, policy=policy)
            for key in NUMERIC_GROSS:
                if not _same_number(recorded[key], fresh[key]):
                    raise ValueError(f"Reproduction mismatch for {label} {policy} {key}")
    return True


def load_tables(development, validation, peer_review, reproduction_dir):
    development, validation = Path(development), Path(validation)
    peer_review, reproduction_dir = Path(peer_review), Path(reproduction_dir)
    verification = json.loads((reproduction_dir / "verification.json").read_text(encoding="utf-8"))
    if verification.get("stage") != "validation" or verification.get("final_test_evaluated") is not False:
        raise ValueError("Refusing a reproduction record that is not a validation-only run")
    peer_gross = read_csv(peer_review / "gross_net_returns.csv")
    reproduced = read_csv(reproduction_dir / "gross_net_returns.csv")
    validation_matches_reproduction(peer_gross, reproduced)
    contrasts, drawdowns, shortfalls, ambiguity, intervals = [], [], [], [], []
    for stage, folder in (("development", development), ("validation", validation)):
        contrasts.extend(_tag(read_csv(folder / "paired_effects.csv"), stage))
        drawdowns.extend(_tag(read_csv(folder / "funded_drawdown.csv"), stage))
        shortfalls.extend(_tag(read_csv(folder / "expected_shortfall.csv"), stage))
        ambiguity.extend(_tag(read_csv(folder / "exit_ambiguity.csv"), stage))
        intervals.extend(_tag(read_csv(folder / "intervals.csv"), stage))
    return dict(
        gross=peer_gross,
        contrasts=contrasts,
        drawdowns=drawdowns,
        shortfalls=shortfalls,
        ambiguity=ambiguity,
        samples=read_csv(peer_review / "sample_accounting.csv"),
        intervals=intervals,
        reproduction=dict(
            run_id=verification["run_id"],
            final_test_evaluated=False,
            maximum_numeric_difference=verification["maximum_numeric_difference"],
        ),
    )


def narrative_from_repository(root=None):
    from path_robust.paths import RUN
    tables = load_tables(
        RUN["DEVELOPMENT"], RUN["VALIDATION"], RUN["PEER_REVIEW"], RUN["M7_VALIDATION"])
    text = render_narrative(**tables)
    if root is not None:
        target = Path(root)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8", newline="\n")
    return text


def main():
    from path_robust.paths import REPORT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=REPORT["M7_RESULTS"] / "RESULTS.md")
    args = parser.parse_args()
    narrative_from_repository(args.output)
    print(args.output)


if __name__ == "__main__":
    main()
