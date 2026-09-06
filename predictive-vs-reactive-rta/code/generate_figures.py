from __future__ import annotations

import argparse
import json
from dataclasses import replace
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter

from single_margin_simulator import Cfg, run_episode


ROOT = Path(__file__).resolve().parent.parent
FIGURES_DIR = ROOT / "figures"
RESULTS_DIR = ROOT / "results"
COORDINATION_RESULTS = RESULTS_DIR / "coordination_validation.json"
COLORS = {
    "blind": "#6c757d",
    "fixed": "#d55e00",
    "predictive": "#0072b2",
    "control": "#333333",
}
NOTE_BOX = {
    "boxstyle": "round,pad=0.18",
    "facecolor": "white",
    "edgecolor": "0.75",
    "alpha": 0.95,
    "linewidth": 0.5,
}

plt.rcParams.update(
    {
        "font.size": 10.5,
        "axes.titlesize": 11,
        "axes.labelsize": 10.5,
        "xtick.labelsize": 9.5,
        "ytick.labelsize": 9.5,
        "legend.fontsize": 8.5,
        "figure.dpi": 160,
        "savefig.dpi": 220,
        "axes.grid": True,
        "axes.axisbelow": True,
        "grid.alpha": 0.25,
        "font.family": "serif",
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
    }
)


def save_figure(figure, stem: str) -> None:
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    for suffix in (".png", ".pdf"):
        figure.savefig(
            FIGURES_DIR / f"{stem}{suffix}",
            bbox_inches="tight",
            facecolor="white",
        )
    plt.close(figure)


def evaluate(
    cfg: Cfg,
    method: str,
    severities,
    seeds,
    *,
    fixed_pad: float = 0.0,
    horizon: float | None = None,
    exponent: float = 1.0,
    condition: str = "conflict",
):
    return [
        run_episode(
            cfg,
            method,
            severity,
            condition,
            seed,
            fixed_pad=fixed_pad,
            horizon=horizon,
            degradation_exponent=exponent,
        )
        for severity in severities
        for seed in seeds
    ]


def summarize(episodes) -> dict:
    count = len(episodes)
    successful = [episode for episode in episodes if episode["successful"]]
    return {
        "episodes": count,
        "collision_count": sum(episode["collision"] for episode in episodes),
        "collision_rate": float(
            np.mean([episode["collision"] for episode in episodes])
        ),
        "successful_count": len(successful),
        "successful_rate": len(successful) / count,
        "mean_successful_elapsed_s": (
            float(np.mean([episode["elapsed_time"] for episode in successful]))
            if successful
            else None
        ),
        "yield_count": sum(episode["yielded"] for episode in episodes),
        "yield_rate": float(np.mean([episode["yielded"] for episode in episodes])),
    }


def best_safe_pad(cfg, exponent, severities, seeds, pads):
    candidates = []
    for pad in pads:
        result = summarize(
            evaluate(
                cfg,
                "fixed_pad",
                severities,
                seeds,
                fixed_pad=pad,
                exponent=exponent,
            )
        )
        if result["successful_count"] == result["episodes"]:
            candidates.append((result["mean_successful_elapsed_s"], pad, result))
    return min(candidates, key=lambda item: (item[0], item[1])) if candidates else None


def mechanism_figure(figure_data: dict) -> None:
    time = np.linspace(0, 10, 400)
    margin_intercept = 3.0
    margin_zero = 7.0
    margin = margin_intercept - (margin_intercept / margin_zero) * time
    predictive_trigger = 5.0
    physical_deadline = 9.0
    recovery_time = 2.5
    latest_safe_trigger = physical_deadline - recovery_time

    figure_data["mechanism"] = {
        "margin_intercept": margin_intercept,
        "margin_zero_time_s": margin_zero,
        "predictive_trigger_time_s": predictive_trigger,
        "reactive_trigger_time_s": margin_zero,
        "physical_deadline_s": physical_deadline,
        "recovery_time_s": recovery_time,
        "latest_safe_trigger_time_s": latest_safe_trigger,
    }

    figure, axis = plt.subplots(figsize=(6.1, 4.65))
    axis.plot(time, margin, color="#222222", linewidth=2.2, label=r"margin $M(t)$")
    axis.axhline(0, color="#666666", linewidth=1)
    axis.axvline(
        margin_zero,
        color=COLORS["fixed"],
        linewidth=2,
        linestyle=(0, (2, 3)),
        label=r"reactive trigger ($M=0$)",
    )
    axis.axvline(
        predictive_trigger,
        color=COLORS["predictive"],
        linewidth=2,
        linestyle=(0, (8, 4)),
        label=r"predictive trigger ($\widehat{T}_A\leq T_h$)",
    )
    axis.axvline(
        latest_safe_trigger,
        color="#555555",
        linewidth=1.8,
        linestyle=":",
        label=r"latest safe trigger $t_{\mathrm{pnr}}=t_f-\tau_r$",
    )
    axis.axvline(
        physical_deadline,
        color="#111111",
        linewidth=2,
        linestyle="-.",
        label=r"physical deadline $t_f$",
    )
    axis.annotate(
        "",
        xy=(margin_zero, 1.0),
        xytext=(predictive_trigger, 1.0),
        arrowprops={"arrowstyle": "<->", "color": COLORS["predictive"]},
    )
    axis.text(
        (predictive_trigger + margin_zero) / 2,
        1.15,
        "lead time $L$",
        color=COLORS["predictive"],
        horizontalalignment="center",
        fontsize=9.5,
        bbox=NOTE_BOX,
    )
    axis.annotate(
        "",
        xy=(physical_deadline, -0.55),
        xytext=(margin_zero, -0.55),
        arrowprops={"arrowstyle": "<->", "color": "#111111"},
    )
    axis.text(
        (margin_zero + physical_deadline) / 2,
        -0.42,
        r"slack $\delta=t_f-t_0$",
        horizontalalignment="center",
        fontsize=9.5,
        bbox=NOTE_BOX,
    )
    axis.add_patch(
        plt.Rectangle(
            (predictive_trigger, -1.35),
            recovery_time,
            0.30,
            facecolor=COLORS["predictive"],
            edgecolor=COLORS["predictive"],
            alpha=0.28,
        )
    )
    axis.text(
        predictive_trigger + recovery_time / 2,
        -1.2,
        r"recovery $\tau_r$ (in time)",
        color=COLORS["predictive"],
        horizontalalignment="center",
        verticalalignment="center",
        fontsize=8.5,
        bbox=NOTE_BOX,
    )
    axis.add_patch(
        plt.Rectangle(
            (margin_zero, -2.0),
            recovery_time,
            0.30,
            facecolor=COLORS["fixed"],
            edgecolor=COLORS["fixed"],
            alpha=0.28,
        )
    )
    axis.text(
        margin_zero + recovery_time / 2,
        -1.85,
        r"recovery $\tau_r$ (too late)",
        color=COLORS["fixed"],
        horizontalalignment="center",
        verticalalignment="center",
        fontsize=8.5,
        bbox=NOTE_BOX,
    )
    axis.set(
        xlabel="time (s)",
        ylabel=r"margin $M$",
        xlim=(0, 10.5),
        ylim=(-2.5, 3.2),
        title=r"Earlier action matters only when $\delta<\tau_r\leq\delta+L$",
    )
    handles, labels = axis.get_legend_handles_labels()
    figure.legend(
        handles,
        labels,
        loc="lower center",
        bbox_to_anchor=(0.5, 0.015),
        ncol=2,
        frameon=True,
        framealpha=1.0,
        edgecolor="0.8",
    )
    figure.subplots_adjust(left=0.12, right=0.98, top=0.91, bottom=0.27)
    save_figure(figure, "fig_mechanism")


def boundary_figure(figure_data: dict) -> None:
    cfg = Cfg()
    pads = (0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0)
    severities = (1, 4, 7, 10, 13)
    seeds = range(25)
    accelerations = (0.5, 0.7, 0.9, 1.2, 1.6, 2.2, 3.0)
    exponents = (0.3, 0.5, 0.7, 0.9, 1.1, 1.4)

    acceleration_rows = []
    for acceleration in accelerations:
        current = replace(cfg, a_max=acceleration)
        predictive = summarize(evaluate(current, "P", severities, seeds))
        fixed = best_safe_pad(current, 1.0, severities, seeds, pads)
        difference = None
        if predictive["successful_count"] == predictive["episodes"] and fixed:
            difference = fixed[0] - predictive["mean_successful_elapsed_s"]
        acceleration_rows.append(
            {
                "a_max": acceleration,
                "selected_fixed_pad": fixed[1] if fixed else None,
                "fixed_mean_successful_elapsed_s": fixed[0] if fixed else None,
                "predictive_mean_successful_elapsed_s": predictive[
                    "mean_successful_elapsed_s"
                ],
                "predictive_collision_count": predictive["collision_count"],
                "finish_time_difference_s": difference,
            }
        )

    exponent_rows = []
    for exponent in exponents:
        current = replace(cfg, a_max=0.8)
        predictive = summarize(
            evaluate(current, "P", severities, seeds, exponent=exponent)
        )
        fixed = best_safe_pad(current, exponent, severities, seeds, pads)
        difference = None
        if predictive["successful_count"] == predictive["episodes"] and fixed:
            difference = fixed[0] - predictive["mean_successful_elapsed_s"]
        exponent_rows.append(
            {
                "degradation_exponent": exponent,
                "selected_fixed_pad": fixed[1] if fixed else None,
                "fixed_mean_successful_elapsed_s": fixed[0] if fixed else None,
                "predictive_mean_successful_elapsed_s": predictive[
                    "mean_successful_elapsed_s"
                ],
                "predictive_collision_count": predictive["collision_count"],
                "finish_time_difference_s": difference,
            }
        )

    figure_data["boundary"] = {
        "source": "code/single_margin_simulator.py",
        "selection": (
            "Within each displayed setting, choose the tested fixed pad with all "
            "episodes successful and minimum mean successful elapsed time."
        ),
        "pads": list(pads),
        "severities": list(severities),
        "seeds_per_severity": len(seeds),
        "prediction_horizon_s": cfg.T_needed,
        "recovery_capability": acceleration_rows,
        "degradation_shape": exponent_rows,
    }

    all_differences = [
        row["finish_time_difference_s"]
        for row in acceleration_rows + exponent_rows
        if row["finish_time_difference_s"] is not None
    ]
    lower = min(-0.2, min(all_differences) - 0.18)
    upper = max(0.2, max(all_differences) + 0.25)
    figure, axes = plt.subplots(1, 2, figsize=(7.25, 3.65), sharey=True)
    for axis in axes:
        axis.axhspan(0, upper, color=COLORS["predictive"], alpha=0.065)
        axis.axhspan(lower, 0, color=COLORS["fixed"], alpha=0.065)
        axis.axhline(0, color="#444444", linewidth=1)
        axis.set_ylim(lower, upper)
        axis.text(
            0.97,
            0.93,
            "+ predictive faster",
            transform=axis.transAxes,
            color=COLORS["predictive"],
            horizontalalignment="right",
            verticalalignment="top",
            fontsize=8,
            bbox=NOTE_BOX,
        )
        axis.text(
            0.03,
            0.07,
            "− fixed pad faster",
            transform=axis.transAxes,
            color=COLORS["fixed"],
            horizontalalignment="left",
            verticalalignment="bottom",
            fontsize=8,
            bbox=NOTE_BOX,
        )

    acceleration_values = [row["finish_time_difference_s"] for row in acceleration_rows]
    axes[0].plot(
        accelerations,
        acceleration_values,
        marker="o",
        color=COLORS["predictive"],
        linewidth=1.8,
        markersize=5,
    )
    axes[0].set(
        xlabel=r"recovery capability $a_{\max}$ (units/s$^2$)",
        ylabel=r"$\overline{t}_{\rm fixed}-\overline{t}_{\rm pred}$ (s)",
        title="(a) Recovery capability",
    )

    safe_rows = [
        row for row in exponent_rows if row["finish_time_difference_s"] is not None
    ]
    axes[1].plot(
        [row["degradation_exponent"] for row in safe_rows],
        [row["finish_time_difference_s"] for row in safe_rows],
        marker="o",
        color=COLORS["predictive"],
        linewidth=1.8,
        markersize=5,
    )
    unsafe_rows = [row for row in exponent_rows if row["predictive_collision_count"]]
    if unsafe_rows:
        marker_y = upper - 0.13 * (upper - lower)
        unsafe_x = [row["degradation_exponent"] for row in unsafe_rows]
        axes[1].scatter(
            unsafe_x,
            [marker_y] * len(unsafe_x),
            marker="x",
            s=55,
            color=COLORS["fixed"],
            linewidth=1.8,
            zorder=5,
        )
        axes[1].text(
            float(np.mean(unsafe_x)),
            marker_y - 0.08 * (upper - lower),
            "collision observed\n(finish time omitted)",
            color=COLORS["fixed"],
            horizontalalignment="center",
            verticalalignment="top",
            fontsize=7.8,
            bbox=NOTE_BOX,
        )
    axes[1].set(xlabel=r"degradation exponent $p$", title="(b) Degradation shape")
    figure.suptitle(
        "Exploratory finish-time difference from a selected fixed pad", fontsize=11.5
    )
    figure.text(
        0.5,
        0.015,
        "Differences are shown only where both methods had zero observed failures.",
        horizontalalignment="center",
        fontsize=8.2,
    )
    figure.subplots_adjust(left=0.11, right=0.99, top=0.82, bottom=0.25, wspace=0.12)
    save_figure(figure, "fig_boundary")


def dose_figure(figure_data: dict) -> None:
    cfg = Cfg()
    severities = (0, 2, 4, 5, 6, 8, 10)
    seeds = range(40)
    methods = {
        "B0": ("uncertainty-blind reactive", "blind", "s", "--"),
        "fixed_pad": (r"reactive at $M=0$", "fixed", "^", "-."),
        "P": ("predictive rate trigger", "predictive", "o", "-"),
    }
    values = {}
    for method in methods:
        values[method] = []
        for severity in severities:
            values[method].append(summarize(evaluate(cfg, method, (severity,), seeds)))

    figure_data["dose_response"] = {
        "source": "code/single_margin_simulator.py",
        "fault_severity_s": list(severities),
        "seeds_per_severity": len(seeds),
        "prediction_horizon_s": cfg.T_needed,
        "methods": values,
    }

    figure, axes = plt.subplots(1, 2, figsize=(7.25, 3.55), sharey=True)
    handles = []
    for method, (label, color_key, marker, linestyle) in methods.items():
        line = axes[0].plot(
            severities,
            [row["successful_rate"] for row in values[method]],
            marker=marker,
            linestyle=linestyle,
            color=COLORS[color_key],
            linewidth=1.8,
            markersize=4.8,
            label=label,
        )[0]
        handles.append(line)
        axes[1].plot(
            severities,
            [row["collision_rate"] for row in values[method]],
            marker=marker,
            linestyle=linestyle,
            color=COLORS[color_key],
            linewidth=1.8,
            markersize=4.8,
        )
    axes[0].set(
        title="(a) Successful completion rate",
        xlabel="fault severity (s)",
        ylabel="fraction of episodes",
        ylim=(-0.05, 1.05),
    )
    axes[1].set(title="(b) Collision rate", xlabel="fault severity (s)")
    figure.suptitle(
        r"Dose response to hidden timing bias ($a_{\max}=1.0$)", fontsize=11.5
    )
    figure.legend(
        handles=handles,
        loc="lower center",
        bbox_to_anchor=(0.5, 0.015),
        ncol=3,
        frameon=True,
        framealpha=1.0,
        edgecolor="0.8",
        fontsize=8,
    )
    figure.subplots_adjust(left=0.10, right=0.99, top=0.80, bottom=0.27, wspace=0.13)
    save_figure(figure, "fig_dose")


def coordination_figure(figure_data: dict) -> None:
    if not COORDINATION_RESULTS.exists():
        raise FileNotFoundError(
            f"Run code/coordination_experiment.py first: {COORDINATION_RESULTS} is missing"
        )
    payload = json.loads(COORDINATION_RESULTS.read_text(encoding="utf-8"))
    rows = {(row["arm"], row["condition"]): row for row in payload["test_summaries"]}
    arms = (
        ("no_intervention", "no intervention", "control", "D"),
        ("fixed_pad_tuned", "selected fixed pad", "fixed", "s"),
        ("predictive_tuned", "selected predictive horizon", "predictive", "o"),
    )
    missing = [
        (arm, condition)
        for arm, _, _, _ in arms
        for condition in ("conflict", "clear")
        if (arm, condition) not in rows
    ]
    if missing:
        raise RuntimeError(f"coordination result rows are missing: {missing}")

    figure_data["coordination"] = {
        "source": "results/coordination_validation.json",
        "selections": payload["selections"],
        "paired_conflict_comparison": payload["paired_conflict_comparison"],
        "test_summaries": payload["test_summaries"],
    }

    y = np.arange(len(arms))[::-1]
    figure, axes = plt.subplots(
        1,
        2,
        figsize=(7.25, 3.65),
        sharey=True,
        gridspec_kw={"width_ratios": (1.05, 1.25)},
    )
    for position, (arm, label, color_key, marker) in zip(y, arms):
        conflict = rows[(arm, "conflict")]
        clear = rows[(arm, "clear")]
        axes[0].scatter(
            conflict["successful_rate"],
            position + 0.10,
            marker=marker,
            s=45,
            color=COLORS[color_key],
            zorder=3,
        )
        axes[0].scatter(
            clear["successful_rate"],
            position - 0.10,
            marker=marker,
            s=42,
            facecolor="white",
            edgecolor=COLORS[color_key],
            linewidth=1.4,
            zorder=3,
        )
        makespan = conflict["mean_successful_makespan_s"]
        if makespan is None:
            axes[1].text(
                0.03,
                position,
                "no successful conflict episodes",
                transform=axes[1].get_yaxis_transform(),
                verticalalignment="center",
                fontsize=8,
                color=COLORS[color_key],
                bbox=NOTE_BOX,
            )
        else:
            axes[1].scatter(
                makespan,
                position,
                marker=marker,
                s=45,
                color=COLORS[color_key],
                zorder=3,
            )
            axes[1].text(
                makespan + 0.15,
                position,
                f"{makespan:.2f} s",
                verticalalignment="center",
                fontsize=8,
                bbox=NOTE_BOX,
            )

    axes[0].set_xlim(-0.05, 1.08)
    axes[0].xaxis.set_major_formatter(PercentFormatter(xmax=1, decimals=0))
    axes[0].set_xlabel("successful completion rate")
    axes[0].set_title("(a) Conflict and clear trials")
    axes[0].set_yticks(y)
    axes[0].set_yticklabels([label for _, label, _, _ in arms])

    successful_times = [
        rows[(arm, "conflict")]["mean_successful_makespan_s"]
        for arm, _, _, _ in arms
        if rows[(arm, "conflict")]["mean_successful_makespan_s"] is not None
    ]
    axes[1].set_xlim(min(successful_times) - 0.6, max(successful_times) + 1.8)
    axes[1].set_xlabel("mean successful conflict makespan (s)")
    axes[1].set_title("(b) Successful conflict trials only")

    handles = [
        plt.Line2D(
            [],
            [],
            marker="o",
            linestyle="none",
            markerfacecolor="0.35",
            markeredgecolor="0.35",
            label="conflict",
        ),
        plt.Line2D(
            [],
            [],
            marker="o",
            linestyle="none",
            markerfacecolor="white",
            markeredgecolor="0.35",
            label="clear",
        ),
    ]
    figure.suptitle("Held-out shared-zone coordination outcomes", fontsize=11.5)
    figure.legend(
        handles=handles,
        loc="lower center",
        bbox_to_anchor=(0.5, 0.015),
        ncol=2,
        frameon=True,
        framealpha=1.0,
        edgecolor="0.8",
    )
    figure.subplots_adjust(left=0.25, right=0.98, top=0.80, bottom=0.24, wspace=0.16)
    save_figure(figure, "fig_coord")


def parse_args():
    parser = argparse.ArgumentParser(description="Regenerate the four paper figures.")
    parser.add_argument(
        "--only",
        choices=("all", "mechanism", "boundary", "dose", "coordination"),
        default="all",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    generators = {
        "mechanism": mechanism_figure,
        "boundary": boundary_figure,
        "dose": dose_figure,
        "coordination": coordination_figure,
    }
    figure_data = {"schema_version": 2}
    selected = generators if args.only == "all" else {args.only: generators[args.only]}
    for name, generator in selected.items():
        generator(figure_data)
        print(f"generated {name}")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = RESULTS_DIR / "figure_data.json"
    if args.only != "all" and output_path.exists():
        previous = json.loads(output_path.read_text(encoding="utf-8"))
        previous.update(figure_data)
        figure_data = previous
    output_path.write_text(
        json.dumps(figure_data, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(f"figure data: {output_path}")


if __name__ == "__main__":
    main()
