from __future__ import annotations

import csv
import json
import platform
import time
from collections import Counter, defaultdict
from dataclasses import asdict, replace
from pathlib import Path

import numpy as np

from coordination_simulator import CoordinationConfig, run_episode


ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = ROOT / "results"
TUNING_REPLICATES = tuple(range(20))
TEST_REPLICATES = tuple(range(60))
MAX_ACCELERATIONS = (0.5, 1.0, 2.5)
DEGRADATION_EXPONENTS = (0.7, 1.0, 1.5)
SEVERITIES_S = (2.0, 6.0, 10.0)
PARAMETER_GRID = tuple(round(float(value), 2) for value in np.arange(0.0, 4.01, 0.25))
BOOTSTRAP_REPLICATES = 20_000
BOOTSTRAP_SEED = 81_377


def simulation_seed(
    split: str,
    condition: str,
    max_acceleration: float,
    degradation_exponent: float,
    severity_s: float,
    replicate: int,
) -> int:
    split_codes = {"tuning": 1, "test": 2}
    condition_codes = {"conflict": 1, "clear": 2}
    if split not in split_codes or condition not in condition_codes:
        raise ValueError("unknown split or condition")
    components = (
        split_codes[split],
        condition_codes[condition],
        int(round(max_acceleration * 100)),
        int(round(degradation_exponent * 100)),
        int(round(severity_s * 100)),
        int(replicate),
    )
    return int(np.random.SeedSequence(components).generate_state(1, dtype=np.uint32)[0])


def scenario_grid():
    for max_acceleration in MAX_ACCELERATIONS:
        for degradation_exponent in DEGRADATION_EXPONENTS:
            for severity_s in SEVERITIES_S:
                yield max_acceleration, degradation_exponent, severity_s


def flatten_episode(
    episode: dict,
    split: str,
    arm: str,
    max_acceleration: float,
    degradation_exponent: float,
    severity_s: float,
    replicate: int,
) -> dict:
    return {
        "split": split,
        "arm": arm,
        "method": episode["method"],
        "parameter": episode["parameter"],
        "condition": episode["condition"],
        "max_acceleration": max_acceleration,
        "degradation_exponent": degradation_exponent,
        "severity_s": severity_s,
        "replicate": replicate,
        "simulation_seed": episode["seed"],
        "reached_goal": int(episode["reached_goal"]),
        "collision": int(episode["collision"]),
        "headway_violation": int(episode["headway_violation"]),
        "timed_out": int(episode["timed_out"]),
        "successful": int(episode["successful"]),
        "makespan_s": episode["makespan_s"],
        "successful_makespan_s": episode["successful_makespan_s"],
        "minimum_entry_headway_s": episode["minimum_entry_headway_s"],
        "serialization_committed": int(episode["serialization_committed"]),
        "serialization_order": (
            "-".join(str(value) for value in episode["serialization_order"])
            if episode["serialization_order"] is not None
            else ""
        ),
        "trigger_time_s": episode["trigger_time_s"],
        "serialization_breaches": episode["serialization_breaches"],
        "yield_events": sum(episode["yield_events_per_robot"]),
        "maximum_yield_events_per_robot": max(episode["yield_events_per_robot"]),
    }


def evaluate_arm(
    arm: str,
    method: str,
    parameter: float,
    split: str,
    condition: str,
    replicates: tuple[int, ...],
) -> list[dict]:
    rows = []
    base = CoordinationConfig()
    no_intervention_templates = {}
    for max_acceleration, degradation_exponent, severity_s in scenario_grid():
        config = replace(base, max_acceleration=max_acceleration)
        for replicate in replicates:
            seed = simulation_seed(
                split,
                condition,
                max_acceleration,
                degradation_exponent,
                severity_s,
                replicate,
            )
            if method == "no_intervention":
                template_key = (condition, max_acceleration)
                if template_key not in no_intervention_templates:
                    no_intervention_templates[template_key] = run_episode(
                        config,
                        method,
                        condition,
                        seed=0,
                    )
                episode = {
                    **no_intervention_templates[template_key],
                    "seed": seed,
                    "severity_s": severity_s,
                    "degradation_exponent": degradation_exponent,
                }
            else:
                episode = run_episode(
                    config,
                    method,
                    condition,
                    seed,
                    parameter=parameter,
                    severity_s=severity_s,
                    degradation_exponent=degradation_exponent,
                )
            rows.append(
                flatten_episode(
                    episode,
                    split,
                    arm,
                    max_acceleration,
                    degradation_exponent,
                    severity_s,
                    replicate,
                )
            )
    return rows


def summarize(rows: list[dict], arm: str, condition: str) -> dict:
    selected = [
        row for row in rows if row["arm"] == arm and row["condition"] == condition
    ]
    n = len(selected)
    successful_times = [
        row["successful_makespan_s"] for row in selected if row["successful"]
    ]
    all_finish_times = [
        row["makespan_s"] for row in selected if row["makespan_s"] is not None
    ]
    trigger_times = [
        row["trigger_time_s"] for row in selected if row["trigger_time_s"] is not None
    ]
    return {
        "arm": arm,
        "condition": condition,
        "n": n,
        "reached_goal_count": sum(row["reached_goal"] for row in selected),
        "collision_count": sum(row["collision"] for row in selected),
        "headway_violation_count": sum(row["headway_violation"] for row in selected),
        "timeout_count": sum(row["timed_out"] for row in selected),
        "successful_count": len(successful_times),
        "successful_rate": len(successful_times) / n,
        "mean_successful_makespan_s": (
            float(np.mean(successful_times)) if successful_times else None
        ),
        "mean_reached_goal_makespan_s": (
            float(np.mean(all_finish_times)) if all_finish_times else None
        ),
        "serialization_count": sum(row["serialization_committed"] for row in selected),
        "serialization_rate": sum(row["serialization_committed"] for row in selected)
        / n,
        "serialization_breach_count": sum(
            row["serialization_breaches"] for row in selected
        ),
        "repeat_yield_episode_count": sum(
            row["maximum_yield_events_per_robot"] > 1 for row in selected
        ),
        "mean_trigger_time_s": float(np.mean(trigger_times)) if trigger_times else None,
    }


def select_candidate(candidate_rows: list[dict]) -> dict:
    full_success = [
        row
        for row in candidate_rows
        if row["successful_count"] == row["n"]
        and row["serialization_breach_count"] == 0
    ]
    if full_success:
        selected = min(
            full_success,
            key=lambda row: (row["mean_successful_makespan_s"], row["parameter"]),
        )
        return {**selected, "selected_from_full_success_pool": True}

    selected = min(
        candidate_rows,
        key=lambda row: (
            -row["successful_count"],
            row["collision_count"]
            + row["headway_violation_count"]
            + row["timeout_count"],
            row["mean_successful_makespan_s"]
            if row["mean_successful_makespan_s"] is not None
            else float("inf"),
            row["parameter"],
        ),
    )
    return {**selected, "selected_from_full_success_pool": False}


def percentile_bootstrap(values: list[float]) -> tuple[float, float]:
    data = np.asarray(values, dtype=float)
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    means = np.empty(BOOTSTRAP_REPLICATES, dtype=float)
    chunk = 1_000
    for start in range(0, BOOTSTRAP_REPLICATES, chunk):
        stop = min(start + chunk, BOOTSTRAP_REPLICATES)
        indices = rng.integers(0, len(data), size=(stop - start, len(data)))
        means[start:stop] = data[indices].mean(axis=1)
    low, high = np.percentile(means, (2.5, 97.5))
    return float(low), float(high)


def paired_comparison(rows: list[dict], fixed_arm: str, predictive_arm: str) -> dict:
    def key(row: dict) -> tuple:
        return (
            row["condition"],
            row["max_acceleration"],
            row["degradation_exponent"],
            row["severity_s"],
            row["replicate"],
        )

    fixed = {key(row): row for row in rows if row["arm"] == fixed_arm}
    predictive = {key(row): row for row in rows if row["arm"] == predictive_arm}
    if fixed.keys() != predictive.keys():
        raise RuntimeError("paired arms have different scenario keys")

    both_success = [
        scenario_key
        for scenario_key in fixed
        if fixed[scenario_key]["successful"] and predictive[scenario_key]["successful"]
    ]
    successful_differences = [
        fixed[scenario_key]["successful_makespan_s"]
        - predictive[scenario_key]["successful_makespan_s"]
        for scenario_key in both_success
    ]
    all_pairs_successful = len(both_success) == len(fixed)
    replicate_differences = []
    if all_pairs_successful:
        for replicate in TEST_REPLICATES:
            replicate_keys = [value for value in fixed if value[-1] == replicate]
            replicate_differences.append(
                float(
                    np.mean(
                        [
                            fixed[value]["successful_makespan_s"]
                            - predictive[value]["successful_makespan_s"]
                            for value in replicate_keys
                        ]
                    )
                )
            )
    interval = (
        percentile_bootstrap(replicate_differences)
        if all_pairs_successful
        else (None, None)
    )
    return {
        "n_pairs": len(fixed),
        "n_replicate_clusters": len(TEST_REPLICATES),
        "both_successful_count": len(both_success),
        "fixed_success_predictive_failure_count": sum(
            fixed[value]["successful"] and not predictive[value]["successful"]
            for value in fixed
        ),
        "predictive_success_fixed_failure_count": sum(
            predictive[value]["successful"] and not fixed[value]["successful"]
            for value in fixed
        ),
        "all_pairs_successful": all_pairs_successful,
        "mean_fixed_minus_predictive_successful_makespan_s": (
            float(np.mean(replicate_differences)) if all_pairs_successful else None
        ),
        "descriptive_mean_among_both_successful_pairs_s": (
            float(np.mean(successful_differences)) if successful_differences else None
        ),
        "paired_bootstrap_ci95_low": interval[0],
        "paired_bootstrap_ci95_high": interval[1],
        "inference_note": (
            "paired interval clusters the fixed scenario grid by test replicate because every pair succeeded"
            if all_pairs_successful
            else "interval suppressed because at least one pair did not have two successful outcomes"
        ),
    }


def seed_audit() -> dict:
    seeds = []
    by_split = defaultdict(set)
    split_specs = (
        ("tuning", ("conflict",), TUNING_REPLICATES),
        ("test", ("conflict", "clear"), TEST_REPLICATES),
    )
    for split, conditions, replicates in split_specs:
        for condition in conditions:
            for max_acceleration, degradation_exponent, severity_s in scenario_grid():
                for replicate in replicates:
                    value = simulation_seed(
                        split,
                        condition,
                        max_acceleration,
                        degradation_exponent,
                        severity_s,
                        replicate,
                    )
                    seeds.append(value)
                    by_split[split].add(value)
    counts = Counter(seeds)
    return {
        "tuple_count": len(seeds),
        "unique_seed_count": len(counts),
        "duplicate_seed_count": sum(count > 1 for count in counts.values()),
        "tuning_test_overlap_count": len(by_split["tuning"] & by_split["test"]),
    }


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def build_report(payload: dict) -> str:
    fixed = payload["selections"]["fixed_pad"]
    predictive = payload["selections"]["predictive_horizon_s"]
    comparison = payload["paired_conflict_comparison"]
    lines = [
        "# Coordination held-out evaluation",
        "",
        "This experiment uses the one-shot serialization state machine in `code/coordination_simulator.py`. It holds out measurement-noise replicates, not scenario families or robot dynamics.",
        "",
        "## Design",
        "",
        f"- Conflict factorial: `{len(MAX_ACCELERATIONS)} x {len(DEGRADATION_EXPONENTS)} x {len(SEVERITIES_S)} = {len(MAX_ACCELERATIONS) * len(DEGRADATION_EXPONENTS) * len(SEVERITIES_S)}` fixed scenarios.",
        f"- Recovery capabilities: `{MAX_ACCELERATIONS}` units/s^2.",
        f"- Degradation exponents: `{DEGRADATION_EXPONENTS}`; hidden-bias severities: `{SEVERITIES_S}` s.",
        f"- Tuning: `{len(TUNING_REPLICATES)}` independent noise replicates per scenario and candidate. Testing: `{len(TEST_REPLICATES)}` seed-disjoint replicates per scenario and arm.",
        f"- Both methods use the grid `{PARAMETER_GRID[0]:.2f}..{PARAMETER_GRID[-1]:.2f}` in `{PARAMETER_GRID[1] - PARAMETER_GRID[0]:.2f}` increments.",
        "- The required entry headway equals nominal physical zone occupancy (0.8333 s). Collision is measured independently from interpolated occupancy-interval overlap.",
        "",
        "## Selection",
        "",
        f"- Fixed reactive pad: `{fixed['parameter']:.2f}` s ({fixed['successful_count']}/{fixed['n']} successful tuning episodes; mean successful makespan `{fixed['mean_successful_makespan_s']:.3f}` s).",
        f"- Predictive horizon: `{predictive['parameter']:.2f}` s ({predictive['successful_count']}/{predictive['n']} successful tuning episodes; mean successful makespan `{predictive['mean_successful_makespan_s']:.3f}` s).",
        "",
        "## Held-out outcomes",
        "",
        "| Arm | Condition | Successful | Collisions | Headway violations | Timeouts | Mean successful makespan | Serializations |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in payload["test_summaries"]:
        makespan = (
            f"{row['mean_successful_makespan_s']:.3f} s"
            if row["mean_successful_makespan_s"] is not None
            else "not defined"
        )
        lines.append(
            f"| {row['arm']} | {row['condition']} | {row['successful_count']}/{row['n']} "
            f"| {row['collision_count']} | {row['headway_violation_count']} "
            f"| {row['timeout_count']} | {makespan} "
            f"| {row['serialization_count']}/{row['n']} |"
        )

    lines.extend(["", "## Paired fixed-versus-predictive comparison", ""])
    if comparison["all_pairs_successful"]:
        lines.append(
            f"All `{comparison['n_pairs']}` conflict pairs succeeded. The mean fixed-minus-predictive successful-makespan difference is `{comparison['mean_fixed_minus_predictive_successful_makespan_s']:.3f}` s; the 95% percentile bootstrap interval clustered over `{comparison['n_replicate_clusters']}` test replicates is `[{comparison['paired_bootstrap_ci95_low']:.3f}, {comparison['paired_bootstrap_ci95_high']:.3f}]` s. Positive values favor prediction. The interval is conditional on the fixed 27-scenario grid."
        )
    else:
        lines.append(
            f"Only `{comparison['both_successful_count']}/{comparison['n_pairs']}` pairs had two successful outcomes. No finish-time interval is reported because safety outcomes differ."
        )

    lines.extend(
        [
            "",
            "## Interpretation limits",
            "",
            "- Successful means that every robot reached the exit with neither physical occupancy overlap nor a required-headway violation.",
            "- A makespan is averaged only over successful episodes; it is not assigned to collisions, headway failures, or timeouts.",
            "- Clear-condition serialization counts are unnecessary interventions and are reported explicitly.",
            "- No-intervention repetitions are deterministic duplicates within a physical scenario and are not independent safety evidence.",
            "- Results generalize over simulated measurement noise conditional on this grid, not to unseen geometries or real robots.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    started = time.perf_counter()
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    tuning_rows = []
    for method in ("fixed_pad", "predictive"):
        for parameter in PARAMETER_GRID:
            arm = f"{method}_{parameter:.2f}"
            trials = evaluate_arm(
                arm,
                method,
                parameter,
                "tuning",
                "conflict",
                TUNING_REPLICATES,
            )
            result = summarize(trials, arm, "conflict")
            result.update({"method": method, "parameter": parameter})
            tuning_rows.append(result)

    fixed = select_candidate(
        [row for row in tuning_rows if row["method"] == "fixed_pad"]
    )
    predictive = select_candidate(
        [row for row in tuning_rows if row["method"] == "predictive"]
    )
    arms = {
        "no_intervention": ("no_intervention", 0.0),
        "fixed_pad_tuned": ("fixed_pad", fixed["parameter"]),
        "predictive_tuned": ("predictive", predictive["parameter"]),
    }

    test_rows = []
    for arm, (method, parameter) in arms.items():
        for condition in ("conflict", "clear"):
            test_rows.extend(
                evaluate_arm(
                    arm,
                    method,
                    parameter,
                    "test",
                    condition,
                    TEST_REPLICATES,
                )
            )

    summaries = [
        summarize(test_rows, arm, condition)
        for arm in arms
        for condition in ("conflict", "clear")
    ]
    conflict_rows = [row for row in test_rows if row["condition"] == "conflict"]
    comparison = paired_comparison(
        conflict_rows,
        "fixed_pad_tuned",
        "predictive_tuned",
    )
    audit = seed_audit()
    if audit["duplicate_seed_count"] or audit["tuning_test_overlap_count"]:
        raise RuntimeError(f"seed audit failed: {audit}")

    elapsed = time.perf_counter() - started
    payload = {
        "schema_version": 1,
        "source": "code/coordination_experiment.py",
        "simulator": "code/coordination_simulator.py",
        "python_version": platform.python_version(),
        "numpy_version": np.__version__,
        "runtime_seconds": elapsed,
        "configuration": asdict(CoordinationConfig()),
        "geometry_note": (
            "Conflict start distances produce overlapping nominal zone occupancy; clear distances "
            "do not. required_headway_s equals nominal_zone_occupancy_s, while collision is measured "
            "from interpolated physical zone-entry and zone-exit intervals."
        ),
        "outcome_definitions": {
            "reached_goal": "all robots reached the configured exit distance",
            "collision": "at least two interpolated physical zone-occupancy intervals overlap",
            "headway_violation": "entry-time separation is below required_headway_s",
            "timed_out": "not all robots reached the exit distance by max_time_s",
            "successful": "reached_goal with no collision and no headway violation",
            "successful_makespan_s": "elapsed time only for successful episodes; null otherwise",
        },
        "design": {
            "tuning_replicates_per_scenario": len(TUNING_REPLICATES),
            "test_replicates_per_scenario": len(TEST_REPLICATES),
            "max_accelerations": MAX_ACCELERATIONS,
            "degradation_exponents": DEGRADATION_EXPONENTS,
            "severities_s": SEVERITIES_S,
            "parameter_grid": PARAMETER_GRID,
            "selection_rule": (
                "Among candidates with 100% successful tuning episodes and no serialization "
                "breaches, minimize successful makespan. If none qualify, explicitly select by "
                "maximum success count before secondary criteria."
            ),
            "held_out_scope": "noise replicates only; the scenario grid is fixed",
            "bootstrap_replicates": BOOTSTRAP_REPLICATES,
            "bootstrap_seed": BOOTSTRAP_SEED,
        },
        "seed_audit": audit,
        "selections": {"fixed_pad": fixed, "predictive_horizon_s": predictive},
        "test_arms": {
            arm: {"method": method, "parameter": parameter}
            for arm, (method, parameter) in arms.items()
        },
        "test_summaries": summaries,
        "paired_conflict_comparison": comparison,
        "interpretation_caveats": [
            (
                "When both selected parameters are zero, predictive and fixed-pad triggering are "
                "the same M <= 0 rule. A zero paired difference is then an algebraic identity, not "
                "evidence that two distinct mechanisms are statistically equivalent."
            ),
            (
                "No-intervention trajectories do not consume measurement noise, so repetitions "
                "within a fixed physical scenario are deterministic duplicates; their counts are "
                "grid coverage, not independent safety evidence."
            ),
            (
                "This validation holds out noise only and must not be interpreted as generalization "
                "to unseen geometries, dynamics, or degradation families."
            ),
            (
                "The controller commits one immutable total crossing order at its first trigger. "
                "The result does not evaluate dynamic replanning or general multi-robot coordination."
            ),
        ],
    }
    (RESULTS_DIR / "coordination_validation.json").write_text(
        json.dumps(payload, indent=2) + "\n",
        encoding="utf-8",
    )
    (RESULTS_DIR / "coordination_validation.md").write_text(
        build_report(payload),
        encoding="utf-8",
    )
    write_csv(RESULTS_DIR / "coordination_validation_tuning.csv", tuning_rows)
    write_csv(RESULTS_DIR / "coordination_validation_trials.csv", test_rows)
    write_csv(RESULTS_DIR / "coordination_validation_summary.csv", summaries)

    print(f"fixed pad: {fixed['parameter']:.2f}")
    print(f"predictive horizon: {predictive['parameter']:.2f} s")
    for row in summaries:
        print(
            f"{row['arm']:20s} {row['condition']:8s} "
            f"success={row['successful_count']}/{row['n']} "
            f"collision={row['collision_count']} headway={row['headway_violation_count']} "
            f"timeout={row['timeout_count']} successful_makespan={row['mean_successful_makespan_s']}"
        )
    print(f"paired conflict: {comparison}")
    print(f"completed in {elapsed:.1f} s")


if __name__ == "__main__":
    main()
