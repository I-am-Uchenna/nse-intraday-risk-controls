"""Build the M7 report tables and headline figures from saved result folders.

Every number in the tables_*.tex files comes from the CSV exports, so the report cannot
drift from the code output. Re-run after the final-test export exists:

    python reports/m7_final/make_tables.py --final results/m7_final_20261112

Without --final, final-test cells are left as visible placeholders.
"""
import argparse
import csv
import shutil
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from path_robust.paths import RUN  # noqa: E402

HERE = Path(__file__).resolve().parent
FIG = HERE / "figures"
REF = "reference"
PRIMARY_PATH = "O-L-H-C"          # stop-first ordering for a long position
LABELS = ("start", "end")
POLICIES = (("time_only", "Time-only"), ("stop_only", "Stop-only"), ("stop_and_target", "Stop and target"))
SETTINGS = (("reference", "Reference"), ("cost_5", "Cost 5 bp"), ("cost_25", "Cost 25 bp"),
            ("stop_slippage_5", "Stop slippage +5 bp"), ("stop_slippage_10", "Stop slippage +10 bp"),
            ("delay_2", "Entry delay 2 min"), ("delay_5", "Entry delay 5 min"))
TBD = r"\TBD"
BLUE, ORANGE = "#2a78d6", "#eb6834"   # validated categorical slots 1 and 2
INK, MUTED = "#0b0b0b", "#52514e"


def rows(folder, name, **match):
    """Read one CSV and keep rows whose columns equal the given values."""
    path = Path(folder) / name
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return [r for r in csv.DictReader(handle) if all(r.get(k) == v for k, v in match.items())]


def one(folder, name, **match):
    found = rows(folder, name, **match)
    if len(found) != 1:
        raise ValueError(f"{folder}/{name}: expected one row for {match}, found {len(found)}")
    return found[0]


def num(value, places=2):
    return f"{float(value):.{places}f}".replace("-", "$-$")


class Stage:
    """One evaluated partition; diagnostics may live in the peer-review folder."""

    def __init__(self, key, title, folder, extra=None):
        self.key, self.title, self.folder = key, title, Path(folder) if folder else None
        self.extra = Path(extra) if extra else None

    @property
    def ready(self):
        return self.folder is not None and (self.folder / "policy_means.csv").exists()

    def diag(self, name, **match):
        """Peer-review style tables: the stage folder first, then the shared folder."""
        found = rows(self.folder, name, stage=self.key, **match) if self.ready else []
        if not found and self.extra:
            found = rows(self.extra, name, stage=self.key, **match)
        if len(found) != 1:
            raise ValueError(f"{self.key}/{name}: expected one row for {match}, found {len(found)}")
        return found[0]


def table(caption, label, colspec, header, body, note):
    return "\n".join([
        r"\begin{table}[htbp]\centering\small",
        rf"\caption{{{caption}}}\label{{{label}}}",
        rf"\begin{{tabular}}{{{colspec}}}\toprule",
        header + r" \\ \midrule",
        *[line + r" \\" for line in body],
        r"\bottomrule\end{tabular}",
        rf"\par\vspace{{3pt}}\begin{{minipage}}{{0.95\linewidth}}\footnotesize\textit{{Note.}} {note}\end{{minipage}}",
        r"\end{table}", ""])


def samples(stages):
    body = []
    for s in stages:
        for lab in LABELS:
            if not s.ready:
                body.append(f"{s.title} & {lab} & {TBD} & {TBD} & {TBD} & {TBD}")
                continue
            r = s.diag("sample_accounting.csv", timestamp_label=lab)
            body.append(f"{s.title} & {lab} & {r['scheduled_days']} & {r['primary_evaluable_days']} & "
                        f"{r['primary_unavailable_days']} & {r['reference_unique_episodes']}")
    return table("Evaluation samples by stage and timestamp interpretation", "tab:samples", "llrrrr",
                 r"Stage & Labels & Scheduled & Complete-case & Unavailable & Episodes", body,
                 "Complete-case sessions have every required signal and policy outcome. Episodes are unique "
                 "reference-execution entries shared by all three exits.")


def gross_net(stages):
    body = []
    for s in stages:
        for lab in LABELS:
            if not s.ready:
                body.append(f"{s.title} & {lab} & {TBD} & {TBD} & {TBD} & {TBD}")
                continue
            r = s.diag("gross_net_returns.csv", timestamp_label=lab, policy="time_only")
            body.append(f"{s.title} & {lab} & {num(r['gross_bp_per_day'])} & {num(r['fee_bp_per_day'])} & "
                        f"{num(r['net_bp_per_day'])} & {num(r['gross_bp_per_trade'])}")
    return table("Time-only gross return against assumed costs", "tab:grossnet", "llrrrr",
                 r"Stage & Labels & Gross bp/day & Fee bp/day & Net bp/day & Gross bp/trade", body,
                 r"Daily values are in basis points of reference capital $C_0=$ INR 100{,}000; per-trade values "
                 r"use entry notional. Reference cost is 15 bp per round trip.")


def policy_means(stages):
    body = []
    for s in stages:
        for lab in LABELS:
            cells = []
            for pol, _ in POLICIES:
                if s.ready:
                    r = one(s.folder, "policy_means.csv", timestamp_label=lab, setting=REF, policy=pol, path=PRIMARY_PATH)
                    cells.append(num(r["mean_daily_pnl_bp"]))
                else:
                    cells.append(TBD)
            body.append(f"{s.title} & {lab} & " + " & ".join(cells))
    return table("Mean net daily P\\&L by exit policy at reference execution", "tab:means", "llrrr",
                 r"Stage & Labels & Time-only & Stop-only & Stop and target", body,
                 r"Basis points of $C_0$ per complete-case session; 15 bp cost, one-minute entry delay, "
                 r"stop-first (O-L-H-C) ordering.")


def primary(stages):
    body, points = [], []
    for s in stages:
        for lab in LABELS:
            if not s.ready:
                body.append(f"{s.title} & {lab} & {TBD} & {TBD} & {TBD}")
                continue
            iv = one(s.folder, "intervals.csv", timestamp_label=lab, path=PRIMARY_PATH,
                     contrast="combined_minus_time", block_length="5")
            body.append(f"{s.title} & {lab} & {iv['n_days']} & {num(iv['mean_difference_bp'], 3)} & "
                        f"[{num(iv['lower_bp'], 3)}, {num(iv['upper_bp'], 3)}]")
            points.append((s.title, lab, float(iv["mean_difference_bp"]), float(iv["lower_bp"]), float(iv["upper_bp"])))
    tex = table("Primary contrast: combined minus time-only", "tab:primary", "llrrc",
                r"Stage & Labels & Days & Mean (bp/day) & Nominal 95\% interval", body,
                r"Paired moving-block percentile interval, five-session blocks, 2{,}000 resamples, seed 17838. "
                r"Intervals are exploratory because the synthetic check in Table~\ref{tab:coverage} shows undercoverage.")
    return tex, points


def risk(stages):
    body = []
    for s in stages:
        for lab in LABELS:
            cells = []
            for pol, _ in POLICIES:
                if s.ready:
                    es = one(s.folder, "expected_shortfall.csv", timestamp_label=lab, path=PRIMARY_PATH, policy=pol)
                    dd = one(s.folder, "funded_drawdown.csv", timestamp_label=lab, path=PRIMARY_PATH, policy=pol)
                    cells += [num(es["ES975_loss_bp"]), num(dd["daily_close_max_drawdown_pct"])]
                else:
                    cells += [TBD, TBD]
            body.append(f"{s.title} & {lab} & " + " & ".join(cells))
    header = (r"& & \multicolumn{2}{c}{Time-only} & \multicolumn{2}{c}{Stop-only} & \multicolumn{2}{c}{Stop and target} \\"
              r" \cmidrule(lr){3-4}\cmidrule(lr){5-6}\cmidrule(lr){7-8}"
              r" Stage & Labels & ES & MDD & ES & MDD & ES & MDD")
    return table("Downside risk: expected shortfall and funded drawdown", "tab:risk", "llrrrrrr", header, body,
                 r"ES is the mean of the worst 2.5\% of daily losses (bp of $C_0$, fractional tail weighting). "
                 r"MDD is the daily-close maximum drawdown (\%) of a continuously funded account.")


def sensitivity(stages):
    ready = [s for s in stages if s.ready or s.extra]
    cols = []
    for s in stages:
        cols += [(s, lab) for lab in LABELS]
    body = []
    for key, name in SETTINGS:
        cells = []
        for s, lab in cols:
            try:
                r = s.diag("execution_sensitivity.csv", timestamp_label=lab, setting=key, contrast="combined_minus_time")
                cells.append(num(r["scenario_difference_bp"], 3))
            except ValueError:
                cells.append(TBD)
        body.append(f"{name} & " + " & ".join(cells))
    groups = " & ".join(rf"\multicolumn{{2}}{{c}}{{{s.title}}}" for s in stages)
    rules = "".join(rf"\cmidrule(lr){{{2 + 2 * i}-{3 + 2 * i}}}" for i in range(len(stages)))
    header = rf"& {groups} \\ {rules} Setting & " + " & ".join(lab for _, lab in cols)
    del ready
    return table("Combined minus time-only under one-at-a-time execution changes", "tab:sensitivity",
                 "l" + "r" * len(cols), header, body,
                 "Basis points of $C_0$ per day on dates common to the scenario and reference execution. "
                 "A common fixed fee cancels in a paired difference, so the two cost rows repeat the reference row.")


def ambiguity(stages):
    body = []
    for s in stages:
        cells = []
        for lab in LABELS:
            if s.ready:
                r = one(s.folder, "exit_ambiguity.csv", timestamp_label=lab)
                cells.append(f"{r['ambiguous_episodes']} / {r['unique_episodes']}")
            else:
                cells.append(TBD)
        body.append(f"{s.title} & " + " & ".join(cells))
    return table("Episodes in which one candle touches both barriers", "tab:ambiguity", "lcc",
                 r"Stage & Start labels & End labels", body,
                 "Ambiguous / unique reference episodes. Only these episodes can rank differently under the two candle orderings.")


def coverage(dev):
    body = []
    for r in rows(dev.folder, "bootstrap_reliability.csv"):
        body.append(f"{r['timestamp_label']} & {float(r['phi']):.1f} & {float(r['coverage_pct']):.1f} "
                    f"({float(r['coverage_mcse_pp']):.2f}) & {float(r['mean_width_over_oracle']):.3f}")
    return table("Synthetic coverage of the nominal 95\\% block-bootstrap interval", "tab:coverage", "lrrr",
                 r"Mask & AR(1) $\phi$ & Coverage \% (MCSE) & Width / oracle", body,
                 "200 simulated zero-mean Gaussian histories per row on the actual development eligibility masks.")


def fig_gross(stages):
    groups, gross, fee = [], [], []
    for s in stages:
        if not (s.ready or s.extra):
            continue
        for lab in LABELS:
            try:
                r = s.diag("gross_net_returns.csv", timestamp_label=lab, policy="time_only")
            except ValueError:
                continue
            groups.append(f"{s.title}\n{lab} labels")
            gross.append(float(r["gross_bp_per_day"]))
            fee.append(float(r["fee_bp_per_day"]))
    fig, ax = plt.subplots(figsize=(6.4, 3.0))
    x = range(len(groups))
    w = 0.38
    ax.bar([i - w / 2 - 0.01 for i in x], gross, w, color=BLUE, label="Gross return before costs")
    ax.bar([i + w / 2 + 0.01 for i in x], fee, w, color=ORANGE, label="Assumed trading cost")
    for i, (g, f) in enumerate(zip(gross, fee)):
        ax.text(i - w / 2, g + (0.05 if g >= 0 else -0.05), f"{g:.2f}", ha="center",
                va="bottom" if g >= 0 else "top", fontsize=8, color=INK)
        ax.text(i + w / 2, f + 0.05, f"{f:.2f}", ha="center", va="bottom", fontsize=8, color=INK)
    ax.set_xticks(list(x), groups, fontsize=8)
    ax.set_ylabel("Basis points of capital per day", fontsize=9)
    ax.set_title("Time-only exit: gross return is far below cost", fontsize=10, color=INK)
    style(ax)
    ax.axhline(0, color=MUTED, lw=0.8)
    ax.set_ylim(min(0, min(gross)) - 0.35, max(fee) * 1.35)
    ax.legend(frameon=False, fontsize=8, loc="upper center", ncol=2)
    save(fig, "gross_vs_cost")


def fig_primary(points):
    fig, ax = plt.subplots(figsize=(6.4, 0.9 + 0.8 * len(dict.fromkeys(p[0] for p in points))))
    titles = list(dict.fromkeys(p[0] for p in points))
    for k, (lab, colour) in enumerate((("start", BLUE), ("end", ORANGE))):
        sel = [p for p in points if p[1] == lab]
        ys = [titles.index(p[0]) + (0.15 if k else -0.15) for p in sel]
        ax.errorbar([p[2] for p in sel], ys, xerr=[[p[2] - p[3] for p in sel], [p[4] - p[2] for p in sel]],
                    fmt="o", ms=6, color=colour, ecolor=colour, elinewidth=2, capsize=0, label=f"{lab} labels")
    ax.axvline(0, color=MUTED, lw=1)
    ax.set_yticks(range(len(titles)), titles, fontsize=9)
    ax.set_xlabel("Combined minus time-only, bp of capital per day (nominal 95% interval)", fontsize=9)
    ax.set_title("Combined minus time-only by stage", fontsize=10, color=INK)
    ax.set_ylim(len(titles) - 0.5, -0.9)
    style(ax, grid="x")
    ax.legend(frameon=False, fontsize=8, loc="upper center", ncol=2)
    save(fig, "primary_contrast")


def style(ax, grid="y"):
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(MUTED)
    ax.tick_params(colors=MUTED, labelsize=8)
    ax.grid(axis=grid, color="#e6e5e0", lw=0.8)
    ax.set_axisbelow(True)


def save(fig, name):
    fig.tight_layout()
    fig.savefig(FIG / f"{name}.pdf")
    fig.savefig(FIG / f"{name}.png", dpi=200)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--final", type=Path, help="final-test results folder, once it exists")
    args = parser.parse_args()
    FIG.mkdir(exist_ok=True)
    dev = Stage("development", "Development", RUN["DEVELOPMENT"], RUN["PEER_REVIEW"])
    val = Stage("validation", "Validation", RUN["M7_VALIDATION"], RUN["PEER_REVIEW"])
    fin = Stage("final", "Final test", args.final)
    stages = (dev, val, fin)
    primary_tex, points = primary(stages)
    parts = {"samples": samples(stages), "grossnet": gross_net(stages), "means": policy_means(stages),
             "primary": primary_tex, "risk": risk(stages), "sensitivity": sensitivity(stages),
             "ambiguity": ambiguity(stages), "coverage": coverage(dev)}
    for name, tex in parts.items():
        (HERE / f"tables_{name}.tex").write_text("% Generated by make_tables.py; do not edit by hand.\n" + tex,
                                                encoding="utf-8")
    fig_gross(stages)
    fig_primary(points)
    for src, dst in ((RUN["M7_VALIDATION"] / "funded_equity_drawdown.png", "validation_funded_equity.png"),
                     (RUN["M7_VALIDATION"] / "execution_sensitivity.png", "validation_execution_sensitivity.png"),
                     (RUN["DEVELOPMENT"] / "coverage.png", "data_coverage.png")):
        shutil.copyfile(src, FIG / dst)
    if fin.ready:
        for name in ("funded_equity_drawdown.png", "paired_effects.png"):
            if (fin.folder / name).exists():
                shutil.copyfile(fin.folder / name, FIG / f"final_{name}")
    print(f"Wrote {len(parts)} tables_*.tex files and figures/ (final stage {'included' if fin.ready else 'pending'})")


if __name__ == "__main__":
    main()
