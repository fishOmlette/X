import csv
import json
import platform
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

from single_margin_simulator import Cfg, run_episode


ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = ROOT / "results"

TUNE_REPLICATES = tuple(range(25))
TEST_REPLICATES = tuple(range(150))
AMAX_VALUES = (0.5, 1.0, 2.5)
CONV_P_VALUES = (0.7, 1.0, 1.5)
SEVERITIES = (2.0, 4.0, 6.0, 8.0, 10.0)
FINE_GRID = tuple(round(value, 2) for value in np.arange(0.0, 4.01, 0.25))
ORIGINAL_PAD_GRID = (0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0)
BOOTSTRAP_REPLICATES = 20_000
BOOTSTRAP_SEED = 73_190


def simulation_seed(split, condition, a_max, conv_p, severity, replicate):
    split_code = {"tuning": 1, "test": 2}[split]
    condition_code = {"conflict": 0, "clear": 1}[condition]
    a_max_index = AMAX_VALUES.index(a_max)
    conv_p_index = CONV_P_VALUES.index(conv_p)
    severity_index = SEVERITIES.index(severity)
    return (
        split_code * 10_000_000
        + condition_code * 1_000_000
        + a_max_index * 100_000
        + conv_p_index * 10_000
        + severity_index * 1_000
        + replicate
    )


def wilson_interval(successes, total, z=1.959963984540054):
    if total == 0:
        return float("nan"), float("nan")
    rate = successes / total
    denom = 1.0 + z * z / total
    center = (rate + z * z / (2.0 * total)) / denom
    half = (
        z * np.sqrt(rate * (1.0 - rate) / total + z * z / (4.0 * total * total)) / denom
    )
    return float(center - half), float(center + half)


def scenario_grid(condition):
    amax_values = AMAX_VALUES if condition == "conflict" else (1.0,)
    for a_max in amax_values:
        for conv_p in CONV_P_VALUES:
            for severity in SEVERITIES:
                yield a_max, conv_p, severity


def candidate_result(method, parameter, replicates):
    collisions = 0
    successes = 0
    elapsed_times = []
    for a_max, conv_p, severity in scenario_grid("conflict"):
        cfg = Cfg(a_max=a_max, T_needed=parameter if method == "P" else Cfg.T_needed)
        for replicate in replicates:
            seed = simulation_seed(
                "tuning", "conflict", a_max, conv_p, severity, replicate
            )
            episode = run_episode(
                cfg,
                method,
                severity,
                "conflict",
                seed,
                fixed_pad=parameter if method == "B2p" else 0.0,
                horizon=parameter if method == "P" else None,
                degradation_exponent=conv_p,
            )
            collisions += int(episode["collision"])
            successes += int(episode["successful"])
            elapsed_times.append(float(episode["elapsed_time"]))
    total = len(elapsed_times)
    ci_low, ci_high = wilson_interval(collisions, total)
    return {
        "method": method,
        "parameter": parameter,
        "n": total,
        "collision_count": collisions,
        "collision_rate": collisions / total,
        "collision_ci95_low": ci_low,
        "collision_ci95_high": ci_high,
        "successful_count": successes,
        "successful_rate": successes / total,
        "mean_elapsed_time_s": float(np.mean(elapsed_times)),
        "sd_elapsed_time_s": float(np.std(elapsed_times, ddof=1)),
    }


def select_candidate(rows, allowed=None):
    eligible = (
        rows
        if allowed is None
        else [row for row in rows if row["parameter"] in allowed]
    )
    zero_collision = [row for row in eligible if row["collision_count"] == 0]
    pool = zero_collision if zero_collision else eligible
    selected = min(
        pool,
        key=lambda row: (row["mean_elapsed_time_s"], row["parameter"]),
    )
    return selected, len(zero_collision)


def evaluate_arm(label, method, parameter):
    trials = []
    for condition in ("conflict", "clear"):
        for a_max, conv_p, severity in scenario_grid(condition):
            cfg = Cfg(
                a_max=a_max, T_needed=parameter if method == "P" else Cfg.T_needed
            )
            for replicate in TEST_REPLICATES:
                seed = simulation_seed(
                    "test", condition, a_max, conv_p, severity, replicate
                )
                episode = run_episode(
                    cfg,
                    method,
                    severity,
                    condition,
                    seed,
                    fixed_pad=parameter if method == "B2p" else 0.0,
                    horizon=parameter if method == "P" else None,
                    degradation_exponent=conv_p,
                )
                trials.append(
                    {
                        "arm": label,
                        "method": method,
                        "parameter": parameter,
                        "condition": condition,
                        "a_max": a_max,
                        "conv_p": conv_p,
                        "severity": severity,
                        "replicate": replicate,
                        "simulation_seed": seed,
                        "reached_goal": int(episode["reached_goal"]),
                        "collision": int(episode["collision"]),
                        "timed_out": int(episode["timed_out"]),
                        "successful": int(episode["successful"]),
                        "yielded": int(episode["yielded"]),
                        "elapsed_time_s": float(episode["elapsed_time"]),
                    }
                )
    return trials


def summarize_trials(trials):
    grouped = defaultdict(list)
    for row in trials:
        exact_key = (
            row["arm"],
            row["condition"],
            row["a_max"],
            row["conv_p"],
            row["severity"],
        )
        pooled_key = (row["arm"], row["condition"], "ALL", "ALL", "ALL")
        grouped[exact_key].append(row)
        grouped[pooled_key].append(row)

    summaries = []
    for key, rows in sorted(
        grouped.items(), key=lambda item: tuple(str(value) for value in item[0])
    ):
        arm, condition, a_max, conv_p, severity = key
        n = len(rows)
        collisions = sum(row["collision"] for row in rows)
        reached_goal = sum(row["reached_goal"] for row in rows)
        timed_out = sum(row["timed_out"] for row in rows)
        successful = sum(row["successful"] for row in rows)
        yielded = sum(row["yielded"] for row in rows)
        coll_low, coll_high = wilson_interval(collisions, n)
        yield_low, yield_high = wilson_interval(yielded, n)
        elapsed_times = np.array([row["elapsed_time_s"] for row in rows], dtype=float)
        successful_elapsed_times = np.array(
            [row["elapsed_time_s"] for row in rows if row["successful"]],
            dtype=float,
        )
        summaries.append(
            {
                "arm": arm,
                "condition": condition,
                "a_max": a_max,
                "conv_p": conv_p,
                "severity": severity,
                "n": n,
                "collision_count": collisions,
                "collision_rate": collisions / n,
                "collision_ci95_low": coll_low,
                "collision_ci95_high": coll_high,
                "reached_goal_count": reached_goal,
                "reached_goal_rate": reached_goal / n,
                "timed_out_count": timed_out,
                "timed_out_rate": timed_out / n,
                "successful_count": successful,
                "successful_rate": successful / n,
                "yield_count": yielded,
                "yield_rate": yielded / n,
                "yield_ci95_low": yield_low,
                "yield_ci95_high": yield_high,
                "mean_elapsed_time_s": float(np.mean(elapsed_times)),
                "sd_elapsed_time_s": float(np.std(elapsed_times, ddof=1)),
                "mean_successful_elapsed_time_s": (
                    float(np.mean(successful_elapsed_times))
                    if len(successful_elapsed_times)
                    else None
                ),
                "sd_successful_elapsed_time_s": (
                    float(np.std(successful_elapsed_times, ddof=1))
                    if len(successful_elapsed_times) > 1
                    else None
                ),
            }
        )
    return summaries


def percentile_bootstrap(values, rng, replicates=BOOTSTRAP_REPLICATES):
    values = np.asarray(values, dtype=float)
    means = np.empty(replicates, dtype=float)
    chunk_size = 1_000
    for start in range(0, replicates, chunk_size):
        stop = min(start + chunk_size, replicates)
        indices = rng.integers(0, len(values), size=(stop - start, len(values)))
        means[start:stop] = values[indices].mean(axis=1)
    low, high = np.percentile(means, [2.5, 97.5])
    return float(low), float(high)


def paired_comparisons(trials, fixed_arm, predictive_arm):
    fixed = {
        (
            row["condition"],
            row["a_max"],
            row["conv_p"],
            row["severity"],
            row["replicate"],
        ): row
        for row in trials
        if row["arm"] == fixed_arm
    }
    predictive = {
        (
            row["condition"],
            row["a_max"],
            row["conv_p"],
            row["severity"],
            row["replicate"],
        ): row
        for row in trials
        if row["arm"] == predictive_arm
    }
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    comparisons = []

    conflict_keys = [key for key in fixed if key[0] == "conflict"]
    exact_groups = defaultdict(list)
    for key in conflict_keys:
        _, a_max, conv_p, severity, _ = key
        exact_groups[(a_max, conv_p, severity)].append(key)

    for (a_max, conv_p, severity), keys in sorted(exact_groups.items()):
        comparisons.append(
            comparison_row(keys, fixed, predictive, rng, a_max, conv_p, severity)
        )

    replicate_differences = []
    fixed_collisions = predictive_collisions = 0
    for replicate in TEST_REPLICATES:
        keys = [key for key in conflict_keys if key[-1] == replicate]
        fixed_collisions += sum(fixed[key]["collision"] for key in keys)
        predictive_collisions += sum(predictive[key]["collision"] for key in keys)
        replicate_differences.append(
            np.mean(
                [
                    fixed[key]["elapsed_time_s"] - predictive[key]["elapsed_time_s"]
                    for key in keys
                ]
            )
        )
    meaningful = fixed_collisions == 0 and predictive_collisions == 0
    if meaningful:
        low, high = percentile_bootstrap(replicate_differences, rng)
        reason = "both arms recorded zero collisions"
    else:
        low = high = None
        reason = "elapsed-time inference is suppressed because at least one arm recorded a collision"
    comparisons.append(
        {
            "scope": "pooled_clustered_by_replicate",
            "a_max": "ALL",
            "conv_p": "ALL",
            "severity": "ALL",
            "n_pairs": len(conflict_keys),
            "n_replicate_clusters": len(TEST_REPLICATES),
            "fixed_collision_count": fixed_collisions,
            "predictive_collision_count": predictive_collisions,
            "mean_fixed_minus_predictive_elapsed_time_s": float(
                np.mean(replicate_differences)
            ),
            "bootstrap_ci95_low": low,
            "bootstrap_ci95_high": high,
            "meaningful_equal_observed_collision_status": meaningful,
            "interpretation": reason,
        }
    )
    return comparisons


def comparison_row(keys, fixed, predictive, rng, a_max, conv_p, severity):
    fixed_collisions = sum(fixed[key]["collision"] for key in keys)
    predictive_collisions = sum(predictive[key]["collision"] for key in keys)
    differences = [
        fixed[key]["elapsed_time_s"] - predictive[key]["elapsed_time_s"] for key in keys
    ]
    meaningful = fixed_collisions == 0 and predictive_collisions == 0
    if meaningful:
        low, high = percentile_bootstrap(differences, rng)
        reason = "both arms recorded zero collisions"
    else:
        low = high = None
        reason = "elapsed-time inference is suppressed because at least one arm recorded a collision"
    return {
        "scope": "scenario",
        "a_max": a_max,
        "conv_p": conv_p,
        "severity": severity,
        "n_pairs": len(keys),
        "n_replicate_clusters": len(keys),
        "fixed_collision_count": fixed_collisions,
        "predictive_collision_count": predictive_collisions,
        "mean_fixed_minus_predictive_elapsed_time_s": float(np.mean(differences)),
        "bootstrap_ci95_low": low,
        "bootstrap_ci95_high": high,
        "meaningful_equal_observed_collision_status": meaningful,
        "interpretation": reason,
    }


def write_csv(path, rows):
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def build_seed_map():
    rows = []
    split_specs = (
        ("tuning", ("conflict",), TUNE_REPLICATES),
        ("test", ("conflict", "clear"), TEST_REPLICATES),
    )
    for split, conditions, replicates in split_specs:
        for condition in conditions:
            for a_max, conv_p, severity in scenario_grid(condition):
                for replicate in replicates:
                    rows.append(
                        {
                            "split": split,
                            "condition": condition,
                            "a_max": a_max,
                            "conv_p": conv_p,
                            "severity": severity,
                            "replicate": replicate,
                            "simulation_seed": simulation_seed(
                                split, condition, a_max, conv_p, severity, replicate
                            ),
                        }
                    )
    seeds = [row["simulation_seed"] for row in rows]
    if len(seeds) != len(set(seeds)):
        raise RuntimeError("simulation seed packing produced a collision")
    return rows


def pooled_summary(summaries, arm, condition):
    return next(
        row
        for row in summaries
        if row["arm"] == arm and row["condition"] == condition and row["a_max"] == "ALL"
    )


def maximum_scenario_collision_bound(summaries, arm, condition):
    rows = [
        row
        for row in summaries
        if row["arm"] == arm and row["condition"] == condition and row["a_max"] != "ALL"
    ]
    worst = max(rows, key=lambda row: row["collision_ci95_high"])
    return {
        "upper": worst["collision_ci95_high"],
        "n_per_scenario": worst["n"],
        "scenario": {
            "a_max": worst["a_max"],
            "conv_p": worst["conv_p"],
            "severity": worst["severity"],
            "collision_count": worst["collision_count"],
            "collision_rate": worst["collision_rate"],
        },
    }


def fmt_interval(low, high, digits=4):
    return f"[{low:.{digits}f}, {high:.{digits}f}]"


def build_report(metadata, summaries, comparisons):
    fixed_arm = metadata["primary_arms"]["fixed"]
    predictive_arm = metadata["primary_arms"]["predictive"]
    fixed_conflict = pooled_summary(summaries, fixed_arm, "conflict")
    pred_conflict = pooled_summary(summaries, predictive_arm, "conflict")
    fixed_clear = pooled_summary(summaries, fixed_arm, "clear")
    pred_clear = pooled_summary(summaries, predictive_arm, "clear")
    pooled = next(
        row for row in comparisons if row["scope"] == "pooled_clustered_by_replicate"
    )
    fixed_bound = maximum_scenario_collision_bound(summaries, fixed_arm, "conflict")
    predictive_bound = maximum_scenario_collision_bound(
        summaries, predictive_arm, "conflict"
    )

    if pooled["bootstrap_ci95_low"] is not None:
        ci_text = fmt_interval(
            pooled["bootstrap_ci95_low"], pooled["bootstrap_ci95_high"], 3
        )
        comparison_text = (
            f"The paired mean elapsed-time difference (fixed minus predictive; positive favors "
            f"prediction) is `{pooled['mean_fixed_minus_predictive_elapsed_time_s']:.3f}` s. Its 95% "
            f"cluster-bootstrap interval is {ci_text}. This interval generalizes over noise "
            f"replicates conditional on the fixed 45-scenario grid. "
            f"{pooled['interpretation'].capitalize()}."
        )
    else:
        comparison_text = (
            f"The raw paired mean elapsed-time difference (fixed minus predictive; positive "
            f"favors prediction) is `{pooled['mean_fixed_minus_predictive_elapsed_time_s']:.3f}` s. It is "
            f"descriptive only: {pooled['interpretation']}, so no bootstrap interval is reported."
        )

    lines = [
        "# Held-out evaluation",
        "",
        "This run separates parameter tuning from testing by independently generated noise replicates. It does not establish real-world safety; it quantifies behavior in the supplied simulator.",
        "",
        "## Design",
        "",
        f"- Tuning replicates: `{metadata['replicates']['tuning']['first']}..{metadata['replicates']['tuning']['last']}` ({metadata['replicates']['tuning']['count']} per scenario).",
        f"- Test replicates: `{metadata['replicates']['test']['first']}..{metadata['replicates']['test']['last']}` ({metadata['replicates']['test']['count']} per scenario).",
        f"- Conflict factorial: {len(AMAX_VALUES)} recovery rates x {len(CONV_P_VALUES)} degradation exponents x {len(SEVERITIES)} severities = {len(AMAX_VALUES) * len(CONV_P_VALUES) * len(SEVERITIES)} scenarios per replicate.",
        "- Each split/scenario/replicate tuple has a distinct deterministic simulation seed; the same tuple is paired across candidates and methods.",
        f"- Both pad and horizon were tuned over `{FINE_GRID[0]:.2f}..{FINE_GRID[-1]:.2f}` in `{FINE_GRID[1] - FINE_GRID[0]:.2f}` increments.",
        "- Selection rule: among candidates with zero tuning collisions, select the one with the lowest mean conflict elapsed time; break ties toward the smaller parameter.",
        "- Exact-scenario collision intervals are two-sided 95% Wilson score intervals. Elapsed-time intervals use a paired percentile bootstrap; the pooled bootstrap resamples replicate indices as conservative clusters across the fixed scenario grid.",
        "",
        "## Selected parameters",
        "",
        f"- Fixed reactive pad: `{metadata['selection']['fixed_pad_fine']['parameter']:.2f}`.",
        f"- Predictive horizon: `{metadata['selection']['predictive_horizon']['parameter']:.2f}` s.",
        f"- Original irregular pad-grid selection: `{metadata['selection']['fixed_pad_original_grid']['parameter']:.2f}`.",
        "",
        "## Held-out pooled results",
        "",
        "| Arm | Conflict collisions | Pooled rate | Max pointwise per-scenario Wilson upper (n=150) | Mean successful elapsed time | Successful conflict runs | Clear false yields | Pooled clear rate |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        f"| Fixed pad | {fixed_conflict['collision_count']}/{fixed_conflict['n']} | {fixed_conflict['collision_rate']:.4f} | {fixed_bound['upper']:.4f} | {fixed_conflict['mean_successful_elapsed_time_s']:.3f} s | {fixed_conflict['successful_count']}/{fixed_conflict['n']} | {fixed_clear['yield_count']}/{fixed_clear['n']} | {fixed_clear['yield_rate']:.4f} |",
        f"| Predictive horizon | {pred_conflict['collision_count']}/{pred_conflict['n']} | {pred_conflict['collision_rate']:.4f} | {predictive_bound['upper']:.4f} | {pred_conflict['mean_successful_elapsed_time_s']:.3f} s | {pred_conflict['successful_count']}/{pred_conflict['n']} | {pred_clear['yield_count']}/{pred_clear['n']} | {pred_clear['yield_rate']:.4f} |",
        "",
        comparison_text,
        "",
        "## Files",
        "",
        "- `heldout_tuning_grid.csv`: every tuning candidate and its selection metrics.",
        "- `heldout_test_trials.csv`: episode-level held-out results.",
        "- `heldout_seed_map.csv`: deterministic simulation seed for every split/scenario/replicate tuple.",
        "- `heldout_test_summary.csv`: exact-scenario and pooled summaries.",
        "- `heldout_paired_comparisons.csv`: paired scenario and pooled elapsed-time comparisons.",
        "- `heldout_evaluation.json`: configuration, selections, headline results, and runtime.",
        "",
        "A zero observed collision count is not a safety proof. The maximum pointwise exact-scenario Wilson upper bound is reported instead of treating the heterogeneous pooled factorial as one binomial sample; it is not a simultaneous confidence bound over all scenarios.",
    ]
    return "\n".join(lines) + "\n"


def main():
    started = time.perf_counter()
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    tuning_rows = []
    for method in ("B2p", "P"):
        for parameter in FINE_GRID:
            row = candidate_result(method, parameter, TUNE_REPLICATES)
            row["split"] = "tuning"
            row["parameter_name"] = "pad" if method == "B2p" else "horizon_s"
            tuning_rows.append(row)
            print(
                f"tune {method:3s} {parameter:4.2f}: "
                f"collisions={row['collision_count']:4d}/{row['n']} "
                f"mean_elapsed={row['mean_elapsed_time_s']:.3f}s",
                flush=True,
            )

    fixed_rows = [row for row in tuning_rows if row["method"] == "B2p"]
    predictive_rows = [row for row in tuning_rows if row["method"] == "P"]
    fixed_fine, fixed_safe_count = select_candidate(fixed_rows)
    fixed_original, fixed_original_safe_count = select_candidate(
        fixed_rows, set(ORIGINAL_PAD_GRID)
    )
    predictive, predictive_safe_count = select_candidate(predictive_rows)

    arms = {
        "fixed_pad_tuned": ("B2p", fixed_fine["parameter"]),
        "predictive_horizon_tuned": ("P", predictive["parameter"]),
    }
    if fixed_original["parameter"] != fixed_fine["parameter"]:
        arms["fixed_pad_original_grid"] = ("B2p", fixed_original["parameter"])
    if predictive["parameter"] != 2.0:
        arms["predictive_horizon_default_2s"] = ("P", 2.0)

    test_trials = []
    for label, (method, parameter) in arms.items():
        print(f"test {label}: {method} parameter={parameter:.2f}", flush=True)
        test_trials.extend(evaluate_arm(label, method, parameter))

    test_summaries = summarize_trials(test_trials)
    comparisons = paired_comparisons(
        test_trials,
        "fixed_pad_tuned",
        "predictive_horizon_tuned",
    )

    tuning_columns = [
        "split",
        "method",
        "parameter_name",
        "parameter",
        "n",
        "collision_count",
        "collision_rate",
        "collision_ci95_low",
        "collision_ci95_high",
        "successful_count",
        "successful_rate",
        "mean_elapsed_time_s",
        "sd_elapsed_time_s",
    ]
    write_csv(
        RESULTS_DIR / "heldout_tuning_grid.csv",
        [{column: row[column] for column in tuning_columns} for row in tuning_rows],
    )
    write_csv(RESULTS_DIR / "heldout_test_trials.csv", test_trials)
    write_csv(RESULTS_DIR / "heldout_seed_map.csv", build_seed_map())
    write_csv(RESULTS_DIR / "heldout_test_summary.csv", test_summaries)
    write_csv(RESULTS_DIR / "heldout_paired_comparisons.csv", comparisons)

    fixed_conflict = pooled_summary(test_summaries, "fixed_pad_tuned", "conflict")
    predictive_conflict = pooled_summary(
        test_summaries, "predictive_horizon_tuned", "conflict"
    )
    fixed_clear = pooled_summary(test_summaries, "fixed_pad_tuned", "clear")
    predictive_clear = pooled_summary(
        test_summaries, "predictive_horizon_tuned", "clear"
    )
    pooled_comparison = next(
        row for row in comparisons if row["scope"] == "pooled_clustered_by_replicate"
    )
    fixed_collision_bound = maximum_scenario_collision_bound(
        test_summaries, "fixed_pad_tuned", "conflict"
    )
    predictive_collision_bound = maximum_scenario_collision_bound(
        test_summaries, "predictive_horizon_tuned", "conflict"
    )

    elapsed = time.perf_counter() - started
    metadata = {
        "schema_version": 2,
        "source": "code/heldout_evaluation.py",
        "simulator": "code/single_margin_simulator.py",
        "python_version": platform.python_version(),
        "numpy_version": np.__version__,
        "runtime_seconds": elapsed,
        "design": {
            "a_max_values": AMAX_VALUES,
            "degradation_exponents": CONV_P_VALUES,
            "severities": SEVERITIES,
            "fine_parameter_grid": FINE_GRID,
            "original_pad_grid": ORIGINAL_PAD_GRID,
            "bootstrap_replicates": BOOTSTRAP_REPLICATES,
            "bootstrap_seed": BOOTSTRAP_SEED,
            "selection_rule": (
                "Among candidates with zero tuning collisions, minimize mean conflict elapsed "
                "time; break ties toward the smaller parameter."
            ),
            "seed_derivation": (
                "Collision-free decimal packing of split code, condition code, a_max index, "
                "degradation-exponent index, severity index, and replicate index. Values remain "
                "below 2^32. Each scenario gets a distinct seed while the same seed is reused "
                "across methods and candidates. Uniqueness is asserted before files are written."
            ),
        },
        "replicates": {
            "tuning": {
                "first": TUNE_REPLICATES[0],
                "last": TUNE_REPLICATES[-1],
                "count": len(TUNE_REPLICATES),
            },
            "test": {
                "first": TEST_REPLICATES[0],
                "last": TEST_REPLICATES[-1],
                "count": len(TEST_REPLICATES),
            },
        },
        "selection": {
            "fixed_pad_fine": {
                **fixed_fine,
                "zero_collision_candidates": fixed_safe_count,
            },
            "fixed_pad_original_grid": {
                **fixed_original,
                "zero_collision_candidates": fixed_original_safe_count,
            },
            "predictive_horizon": {
                **predictive,
                "zero_collision_candidates": predictive_safe_count,
            },
        },
        "primary_arms": {
            "fixed": "fixed_pad_tuned",
            "predictive": "predictive_horizon_tuned",
        },
        "test_arms": {
            label: {"method": method, "parameter": parameter}
            for label, (method, parameter) in arms.items()
        },
        "headline_results": {
            "fixed_conflict": fixed_conflict,
            "fixed_max_scenario_collision_wilson_upper": fixed_collision_bound,
            "predictive_conflict": predictive_conflict,
            "predictive_max_scenario_collision_wilson_upper": predictive_collision_bound,
            "fixed_clear": fixed_clear,
            "predictive_clear": predictive_clear,
            "paired_elapsed_time": pooled_comparison,
        },
        "limitations": [
            "The test noise replicates are held out, but the simulator family and scenario grid are fixed in advance.",
            "Zero observed collisions do not establish safety.",
            "The comparison does not include ROS 2, Nav2, hardware, perception failures, or dynamics outside the supplied simulator.",
            "Elapsed-time inference is reported only when both compared arms have zero observed collisions in the relevant subset.",
            "Any pooled elapsed-time interval, when reported, generalizes over noise replicates conditional on the fixed scenario grid, not over a population of scenarios.",
        ],
    }
    (RESULTS_DIR / "heldout_evaluation.json").write_text(
        json.dumps(metadata, indent=2) + "\n",
        encoding="utf-8",
    )
    (RESULTS_DIR / "heldout_evaluation.md").write_text(
        build_report(metadata, test_summaries, comparisons),
        encoding="utf-8",
    )

    print(f"completed in {elapsed:.1f}s; results -> {RESULTS_DIR}", flush=True)


if __name__ == "__main__":
    main()
