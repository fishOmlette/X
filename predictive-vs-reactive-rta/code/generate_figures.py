from __future__ import annotations

import argparse
import json
from dataclasses import replace
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from single_margin_simulator import Cfg, run_episode


ROOT = Path(__file__).resolve().parent.parent
FIGURES_DIR = ROOT / "figures"
RESULTS_DIR = ROOT / "results"
COLUMN_WIDTH_IN = 3.45
COLORS = {
    "blind": "#6c757d",
    "fixed": "#d55e00",
    "predictive": "#0072b2",
}

plt.rcParams.update(
    {
        "font.size": 8,
        "axes.titlesize": 8,
        "axes.labelsize": 8,
        "xtick.labelsize": 7,
        "ytick.labelsize": 7,
        "legend.fontsize": 7,
        "axes.linewidth": 0.6,
        "xtick.major.width": 0.6,
        "ytick.major.width": 0.6,
        "figure.dpi": 200,
        "axes.grid": True,
        "axes.axisbelow": True,
        "grid.alpha": 0.25,
        "grid.linewidth": 0.5,
        "font.family": "serif",
        "font.serif": ["Times New Roman", "Nimbus Roman", "Liberation Serif", "DejaVu Serif"],
        "mathtext.fontset": "stix",
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
    }
)


def save_figure(figure, stem: str) -> None:
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    figure.savefig(
        FIGURES_DIR / f"{stem}.pdf",
        bbox_inches="tight",
        pad_inches=0.02,
        facecolor="white",
        metadata={"CreationDate": None, "ModDate": None},
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

    figure, axis = plt.subplots(figsize=(COLUMN_WIDTH_IN, 2.85))
    axis.plot(time, margin, color="#222222", linewidth=1.5, label=r"margin $M(t)$")
    axis.axhline(0, color="#666666", linewidth=0.8)
    axis.axvline(
        margin_zero,
        color=COLORS["fixed"],
        linewidth=1.3,
        linestyle=(0, (2, 2)),
        label=r"reactive trigger at $t_0$ ($M=0$)",
    )
    axis.axvline(
        predictive_trigger,
        color=COLORS["predictive"],
        linewidth=1.3,
        linestyle=(0, (6, 3)),
        label=r"predictive trigger ($M/\hat{r}=T_h$)",
    )
    axis.axvline(
        latest_safe_trigger,
        color="#555555",
        linewidth=1.2,
        linestyle=":",
        label=r"latest safe trigger $t_{\mathrm{pnr}}=t_f-\tau_r$",
    )
    axis.axvline(
        physical_deadline,
        color="#111111",
        linewidth=1.3,
        linestyle="-.",
        label=r"physical deadline $t_f$",
    )
    axis.annotate(
        "",
        xy=(margin_zero, 1.6),
        xytext=(predictive_trigger, 1.6),
        arrowprops={"arrowstyle": "<->", "color": COLORS["predictive"], "lw": 0.8},
    )
    axis.text(
        predictive_trigger + 0.7,
        1.75,
        "lead $L$",
        color=COLORS["predictive"],
        horizontalalignment="center",
        verticalalignment="bottom",
        fontsize=7,
    )
    axis.annotate(
        "",
        xy=(physical_deadline, 0.35),
        xytext=(margin_zero, 0.35),
        arrowprops={"arrowstyle": "<->", "color": "#111111", "lw": 0.8},
    )
    axis.text(
        (margin_zero + physical_deadline) / 2,
        0.5,
        r"slack $\delta$",
        horizontalalignment="center",
        verticalalignment="bottom",
        fontsize=7,
    )
    axis.add_patch(
        plt.Rectangle(
            (predictive_trigger, -1.50),
            recovery_time,
            0.30,
            facecolor="#d2e5f3",
            edgecolor=COLORS["predictive"],
            linewidth=0.6,
            zorder=3,
        )
    )
    axis.text(
        predictive_trigger + recovery_time / 2,
        -1.35,
        r"$\tau_r$ in time",
        color=COLORS["predictive"],
        horizontalalignment="center",
        verticalalignment="center",
        fontsize=6.5,
        zorder=4,
    )
    axis.add_patch(
        plt.Rectangle(
            (margin_zero, -2.10),
            recovery_time,
            0.30,
            facecolor="#f8dcc5",
            edgecolor=COLORS["fixed"],
            linewidth=0.6,
            zorder=3,
        )
    )
    axis.text(
        margin_zero + recovery_time / 2,
        -1.95,
        r"$\tau_r$ too late",
        color=COLORS["fixed"],
        horizontalalignment="center",
        verticalalignment="center",
        fontsize=6.5,
        zorder=4,
    )
    axis.set(
        xlabel="time (s)",
        ylabel=r"margin $M$",
        xlim=(0, 10.5),
        ylim=(-2.5, 3.2),
    )
    handles, labels = axis.get_legend_handles_labels()
    axis.legend(
        handles,
        labels,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.2),
        ncol=2,
        frameon=False,
        handlelength=2.2,
        columnspacing=1.0,
        fontsize=6.5,
    )
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
    upper = max(0.2, max(all_differences) + 0.35)
    figure, axes = plt.subplots(
        1, 2, figsize=(COLUMN_WIDTH_IN, 2.15), sharey=True, layout="constrained"
    )
    for axis in axes:
        axis.axhspan(0, upper, color=COLORS["predictive"], alpha=0.065)
        axis.axhspan(lower, 0, color=COLORS["fixed"], alpha=0.065)
        axis.axhline(0, color="#444444", linewidth=0.8)
        axis.set_ylim(lower, upper)
        axis.text(
            0.96,
            0.95,
            "+ prediction faster",
            transform=axis.transAxes,
            color=COLORS["predictive"],
            horizontalalignment="right",
            verticalalignment="top",
            fontsize=6,
        )
        axis.text(
            0.04,
            0.05,
            "\u2212 fixed pad faster",
            transform=axis.transAxes,
            color=COLORS["fixed"],
            horizontalalignment="left",
            verticalalignment="bottom",
            fontsize=6,
        )

    acceleration_values = [row["finish_time_difference_s"] for row in acceleration_rows]
    axes[0].plot(
        accelerations,
        acceleration_values,
        marker="o",
        color=COLORS["predictive"],
        linewidth=1.2,
        markersize=3.5,
    )
    axes[0].set(
        xlabel=r"$a_{\max}$ (units/s$^2$)",
        ylabel=r"$\overline{t}_{\mathrm{fixed}}-\overline{t}_{\mathrm{pred}}$ (s)",
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
        linewidth=1.2,
        markersize=3.5,
    )
    unsafe_rows = [row for row in exponent_rows if row["predictive_collision_count"]]
    if unsafe_rows:
        marker_y = 0.5 * upper
        unsafe_x = [row["degradation_exponent"] for row in unsafe_rows]
        no_safe_pad = all(row["selected_fixed_pad"] is None for row in unsafe_rows)
        axes[1].scatter(
            unsafe_x,
            [marker_y] * len(unsafe_x),
            marker="x",
            s=22,
            color=COLORS["fixed"],
            linewidth=1.2,
            zorder=5,
        )
        axes[1].text(
            min(unsafe_x) - 0.04,
            marker_y - 0.06 * (upper - lower),
            "both rules fail" if no_safe_pad else "prediction collides",
            color=COLORS["fixed"],
            horizontalalignment="left",
            verticalalignment="top",
            fontsize=6,
        )
    axes[1].set(xlabel=r"degradation exponent $p$", title="(b) Degradation shape")
    save_figure(figure, "fig_boundary")


def dose_figure(figure_data: dict) -> None:
    cfg = Cfg()
    severities = (0, 2, 4, 5, 6, 8, 10)
    seeds = range(40)
    methods = {
        "B0": ("uncertainty-blind", "blind", "s", "--"),
        "fixed_pad": (r"reactive, $M\leq 0$", "fixed", "^", "-."),
        "P": (r"predictive, $T_h=2$ s", "predictive", "o", "-"),
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

    figure, axes = plt.subplots(
        1, 2, figsize=(COLUMN_WIDTH_IN, 2.3), sharey=True, layout="constrained"
    )
    handles = []
    for method, (label, color_key, marker, linestyle) in methods.items():
        line = axes[0].plot(
            severities,
            [row["successful_rate"] for row in values[method]],
            marker=marker,
            linestyle=linestyle,
            color=COLORS[color_key],
            linewidth=1.2,
            markersize=3.5,
            label=label,
        )[0]
        handles.append(line)
        axes[1].plot(
            severities,
            [row["collision_rate"] for row in values[method]],
            marker=marker,
            linestyle=linestyle,
            color=COLORS[color_key],
            linewidth=1.2,
            markersize=3.5,
        )
    axes[0].set(
        title="(a) Successful completion",
        xlabel="fault severity (s)",
        ylabel="fraction of episodes",
        ylim=(-0.05, 1.05),
    )
    axes[1].set(title="(b) Collision", xlabel="fault severity (s)")
    figure.legend(
        handles=handles,
        loc="outside lower center",
        ncol=3,
        frameon=False,
        handlelength=2.2,
        columnspacing=1.0,
        fontsize=6.5,
    )
    save_figure(figure, "fig_dose")


def parse_args():
    parser = argparse.ArgumentParser(description="Regenerate the three paper figures.")
    parser.add_argument(
        "--only",
        choices=("all", "mechanism", "boundary", "dose"),
        default="all",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    generators = {
        "mechanism": mechanism_figure,
        "boundary": boundary_figure,
        "dose": dose_figure,
    }
    figure_data = {"schema_version": 3}
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
