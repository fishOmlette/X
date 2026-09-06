import csv
import json
import time
from pathlib import Path

import numpy as np

from legacy_coordination_simulator import Cfg, DEFAULT_PADS, DEFAULT_SEEDS, theil_sen


ROOT = Path(__file__).resolve().parents[2]
RESULTS_DIR = ROOT / "results" / "legacy"


def run_episode_variant(
    cfg,
    method,
    sev_scale,
    hetero,
    condition,
    seed,
    pad=0.0,
    conv_p=1.0,
    reentry_after_release=False,
):
    rng = np.random.default_rng(seed)
    d0 = np.array(cfg.d0 if condition == "conflict" else cfg.d0_clear, float)
    s = d0.copy()
    v = np.full(cfg.N, cfg.v_nom)
    sev = sev_scale * (np.array(cfg.hetero_pattern) if hetero else np.ones(cfg.N))
    yielding = np.zeros(cfg.N, bool)
    released = np.zeros(cfg.N, bool)
    yield_for = -np.ones(cfg.N, int)
    yield_counts = np.zeros(cfg.N, int)
    collision = False
    margins, times = [], []

    def perceive():
        arrival = (s - cfg.R_zone) / np.maximum(v, 0.05)
        fraction = np.clip((s - cfg.R_zone) / (d0 - cfg.R_zone), 0, 1)
        bias = sev * (fraction**conv_p)
        sigma = cfg.sigma0 + cfg.sigma_range * fraction
        return arrival + bias, sigma

    def coordination_margin(active):
        estimated_arrival, sigma = perceive()
        candidates = [index for index in active if s[index] > cfg.R_zone]
        if len(candidates) < 2:
            return np.inf, None
        best_margin, binding_pair = np.inf, None
        for left_pos in range(len(candidates)):
            for right_pos in range(left_pos + 1, len(candidates)):
                left = candidates[left_pos]
                right = candidates[right_pos]
                headway = (
                    abs(estimated_arrival[left] - estimated_arrival[right])
                    - cfg.k_sigma * (sigma[left] + sigma[right])
                    - cfg.H_req
                )
                if headway < best_margin:
                    best_margin = headway
                    later = (
                        left
                        if estimated_arrival[left] > estimated_arrival[right]
                        else right
                    )
                    binding_pair = (left, right, later)
        return best_margin, binding_pair

    for step in range(int(cfg.T_max / cfg.dt)):
        t = step * cfg.dt
        active = [index for index in range(cfg.N) if not yielding[index]]
        margin, pair = coordination_margin(active)
        noisy_margin = (
            margin + rng.normal(0, cfg.meas_noise) if np.isfinite(margin) else margin
        )
        margins.append(
            noisy_margin
            if np.isfinite(noisy_margin)
            else (margins[-1] if margins else 5.0)
        )
        times.append(t)

        trigger = False
        if pair is not None:
            if method == "B0":
                estimated_arrival, _ = perceive()
                left, right, _ = pair
                trigger = (
                    abs(estimated_arrival[left] - estimated_arrival[right]) < cfg.H_req
                )
            elif method == "B2p":
                trigger = noisy_margin <= pad
            elif method == "P":
                window = cfg.slope_window
                slope = (
                    theil_sen(times[-window:], margins[-window:])
                    if len(margins) >= 2
                    else 0.0
                )
                predicted_time = noisy_margin / -slope if slope < -1e-3 else np.inf
                trigger = predicted_time <= cfg.T_needed or noisy_margin <= 0
            else:
                raise ValueError(method)

        if trigger and pair is not None:
            _, _, later = pair
            earlier = pair[0] if pair[1] == later else pair[1]
            if not yielding[later]:
                yielding[later] = True
                released[later] = False
                yield_for[later] = earlier
                yield_counts[later] += 1

        for index in range(cfg.N):
            target = cfg.v_nom
            if yielding[index]:
                if released[index]:
                    target = cfg.v_nom
                else:
                    target = 0.0
                    leader = yield_for[index]
                    if leader < 0 or s[leader] < -cfg.R_zone:
                        if reentry_after_release:
                            yielding[index] = False
                            yield_for[index] = -1
                        else:
                            released[index] = True
                        target = cfg.v_nom
            delta_v = np.clip(
                target - v[index],
                -cfg.a_max * cfg.dt,
                cfg.a_max * cfg.dt,
            )
            v[index] = max(0.0, v[index] + delta_v)
            s[index] -= v[index] * cfg.dt

        if np.sum(np.abs(s) < cfg.R_zone) >= 2:
            collision = True
        if np.all(s <= -cfg.exit_dist):
            break

    reached_exit = bool(np.all(s <= -cfg.exit_dist))
    return {
        "collision": bool(collision),
        "completed": bool(reached_exit and not collision),
        "timed_out": not reached_exit,
        "t_done": float(t),
        "yield_events": int(np.sum(yield_counts)),
        "robots_yielding_more_than_once": int(np.sum(yield_counts > 1)),
    }


def run_episode_with_reentry(
    cfg, method, sev_scale, hetero, condition, seed, pad=0.0, conv_p=1.0
):
    return run_episode_variant(
        cfg, method, sev_scale, hetero, condition, seed, pad, conv_p, True
    )


def pooled_variant(
    cfg, method, hetero, pad, conv_p, sev_scales, seeds, reentry_after_release
):
    collisions, completions, timeouts, finishes, yield_events, repeaters = (
        [],
        [],
        [],
        [],
        [],
        [],
    )
    for scale in sev_scales:
        for seed in range(seeds):
            result = run_episode_variant(
                cfg,
                method,
                scale,
                hetero,
                "conflict",
                seed,
                pad,
                conv_p,
                reentry_after_release,
            )
            collisions.append(result["collision"])
            completions.append(result["completed"])
            timeouts.append(result["timed_out"])
            finishes.append(result["t_done"])
            yield_events.append(result["yield_events"])
            repeaters.append(result["robots_yielding_more_than_once"])
    completed_finishes = [
        finish for finish, completed in zip(finishes, completions) if completed
    ]
    return {
        "collision_count": int(np.sum(collisions)),
        "n": len(collisions),
        "collision_rate": float(np.mean(collisions)),
        "completion_count": int(np.sum(completions)),
        "completion_rate": float(np.mean(completions)),
        "timeout_count": int(np.sum(timeouts)),
        "mean_finish_all_s": float(np.mean(finishes)),
        "mean_finish_completed_s": (
            float(np.mean(completed_finishes)) if completed_finishes else None
        ),
        "mean_yield_events": float(np.mean(yield_events)),
        "episodes_with_repeat_yield": int(np.sum(np.asarray(repeaters) > 0)),
    }


def pad_grid_variant(
    cfg, hetero, conv_p, sev_scales, seeds, pads, reentry_after_release
):
    candidates = []
    for pad in pads:
        result = pooled_variant(
            cfg,
            "B2p",
            hetero,
            pad,
            conv_p,
            sev_scales,
            seeds,
            reentry_after_release,
        )
        candidates.append({"pad": pad, **result})
    fully_successful = [
        candidate
        for candidate in candidates
        if candidate["collision_count"] == 0 and candidate["timeout_count"] == 0
    ]
    if fully_successful:
        selected = min(
            fully_successful,
            key=lambda candidate: (
                candidate["mean_finish_completed_s"],
                candidate["pad"],
            ),
        )
        criterion = (
            "zero collisions and zero timeouts; minimum conditional completion time"
        )
    else:
        selected = min(
            candidates,
            key=lambda candidate: (
                candidate["collision_count"],
                candidate["timeout_count"],
                candidate["mean_finish_completed_s"]
                if candidate["mean_finish_completed_s"] is not None
                else np.inf,
                candidate["pad"],
            ),
        )
        criterion = (
            "fallback: lexicographic collisions, timeouts, conditional completion time"
        )
    return selected, candidates, criterion


def main():
    started = time.perf_counter()
    cfg = Cfg()
    cases = (
        (False, "homogeneous", (2, 3), "narrow", 1.0),
        (False, "homogeneous", (1, 2, 3, 4, 5, 6), "wide", 1.0),
        (True, "heterogeneous", (2, 3), "narrow", 1.0),
        (True, "heterogeneous", (1, 2, 3, 4, 5, 6), "wide", 1.0),
        (True, "heterogeneous", (1, 2, 3, 4, 5, 6), "wide_shape_0.3", 0.3),
        (True, "heterogeneous", (1, 2, 3, 4, 5, 6), "wide_shape_2.0", 2.0),
    )
    summary_rows = []
    pad_rows = []

    for hetero, group, scales, range_name, conv_p in cases:
        original_prediction = pooled_variant(
            cfg, "P", hetero, 0.0, conv_p, scales, DEFAULT_SEEDS, False
        )
        corrected_prediction = pooled_variant(
            cfg, "P", hetero, 0.0, conv_p, scales, DEFAULT_SEEDS, True
        )
        original_pad, original_candidates, original_criterion = pad_grid_variant(
            cfg, hetero, conv_p, scales, DEFAULT_SEEDS, DEFAULT_PADS, False
        )
        corrected_pad, corrected_candidates, corrected_criterion = pad_grid_variant(
            cfg, hetero, conv_p, scales, DEFAULT_SEEDS, DEFAULT_PADS, True
        )
        corrected_at_original_pad = next(
            candidate
            for candidate in corrected_candidates
            if candidate["pad"] == original_pad["pad"]
        )

        case_name = f"{group}_{range_name}"
        summary_rows.append(
            {
                "case": case_name,
                "heterogeneous": hetero,
                "conv_p": conv_p,
                "severity_scales": ";".join(str(value) for value in scales),
                "n": len(scales) * DEFAULT_SEEDS,
                "original_predictive_collision_count": original_prediction[
                    "collision_count"
                ],
                "original_predictive_completion_count": original_prediction[
                    "completion_count"
                ],
                "original_predictive_timeout_count": original_prediction[
                    "timeout_count"
                ],
                "original_predictive_mean_finish_completed_s": original_prediction[
                    "mean_finish_completed_s"
                ],
                "corrected_predictive_collision_count": corrected_prediction[
                    "collision_count"
                ],
                "corrected_predictive_completion_count": corrected_prediction[
                    "completion_count"
                ],
                "corrected_predictive_timeout_count": corrected_prediction[
                    "timeout_count"
                ],
                "corrected_predictive_mean_finish_completed_s": corrected_prediction[
                    "mean_finish_completed_s"
                ],
                "corrected_predictive_mean_yield_events": corrected_prediction[
                    "mean_yield_events"
                ],
                "corrected_predictive_episodes_with_repeat_yield": corrected_prediction[
                    "episodes_with_repeat_yield"
                ],
                "original_selected_pad": original_pad["pad"],
                "original_pad_selection_criterion": original_criterion,
                "original_selected_pad_collision_count": original_pad[
                    "collision_count"
                ],
                "original_selected_pad_completion_count": original_pad[
                    "completion_count"
                ],
                "original_selected_pad_timeout_count": original_pad["timeout_count"],
                "original_selected_pad_mean_finish_completed_s": original_pad[
                    "mean_finish_completed_s"
                ],
                "corrected_at_original_pad_collision_count": corrected_at_original_pad[
                    "collision_count"
                ],
                "corrected_at_original_pad_completion_count": corrected_at_original_pad[
                    "completion_count"
                ],
                "corrected_at_original_pad_timeout_count": corrected_at_original_pad[
                    "timeout_count"
                ],
                "corrected_at_original_pad_mean_finish_completed_s": corrected_at_original_pad[
                    "mean_finish_completed_s"
                ],
                "corrected_selected_pad": corrected_pad["pad"],
                "corrected_pad_selection_criterion": corrected_criterion,
                "corrected_selected_pad_collision_count": corrected_pad[
                    "collision_count"
                ],
                "corrected_selected_pad_completion_count": corrected_pad[
                    "completion_count"
                ],
                "corrected_selected_pad_timeout_count": corrected_pad["timeout_count"],
                "corrected_selected_pad_mean_finish_completed_s": corrected_pad[
                    "mean_finish_completed_s"
                ],
                "corrected_selected_pad_mean_yield_events": corrected_pad[
                    "mean_yield_events"
                ],
                "corrected_selected_pad_episodes_with_repeat_yield": corrected_pad[
                    "episodes_with_repeat_yield"
                ],
            }
        )
        for state, candidates in (
            ("original_permanent_exclusion", original_candidates),
            ("reentry_after_release", corrected_candidates),
        ):
            for candidate in candidates:
                pad_rows.append(
                    {
                        "case": case_name,
                        "state_handling": state,
                        "conv_p": conv_p,
                        **candidate,
                    }
                )
        print(
            f"{case_name}: P C/K/T "
            f"{original_prediction['collision_count']}/{original_prediction['completion_count']}/{original_prediction['timeout_count']} -> "
            f"{corrected_prediction['collision_count']}/{corrected_prediction['completion_count']}/{corrected_prediction['timeout_count']}; "
            f"pad {original_pad['pad']}->{corrected_pad['pad']}",
            flush=True,
        )

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    with (RESULTS_DIR / "coordination_state_audit.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summary_rows[0]))
        writer.writeheader()
        writer.writerows(summary_rows)
    with (RESULTS_DIR / "coordination_state_audit_pad_grid.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(pad_rows[0]))
        writer.writeheader()
        writer.writerows(pad_rows)

    elapsed = time.perf_counter() - started
    payload = {
        "schema_version": 1,
        "source": "code/legacy/audit_coordination_state.py",
        "original_simulator": "code/legacy/legacy_coordination_simulator.py",
        "runtime_seconds": elapsed,
        "seeds": {"first": 0, "last": DEFAULT_SEEDS - 1, "count": DEFAULT_SEEDS},
        "state_change": (
            "A robot is active again after its blocking robot clears the zone. "
            "A subsequent trigger starts a new yield cycle."
        ),
        "why_audit_was_needed": (
            "The original state keeps yielding=True after release, so that robot is permanently "
            "excluded from active pair selection even while it is still approaching the shared zone."
        ),
        "results": summary_rows,
        "interpretation": (
            "This is a model-correction sensitivity audit, not an additional held-out experiment. "
            "Any manuscript result using the corrected transition must be labeled and rerun under "
            "a predeclared tuning/test split."
        ),
    }
    (RESULTS_DIR / "coordination_state_audit.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )

    lines = [
        "# Coordination state-transition audit",
        "",
        payload["why_audit_was_needed"],
        "",
        "The audit makes a released robot eligible for pair selection again and starts a fresh yield cycle if it is selected later. No existing simulator file was changed.",
        "",
        "`C/K/T` denotes collision count, collision-free completion count, and timeout count. Finish time is averaged only over collision-free completed episodes.",
        "",
        "| Case | n | P C/K/T old -> corrected | P completed finish old -> corrected | Selected pad old -> corrected | Fixed-pad C/K/T old -> corrected | Fixed-pad completed finish old -> corrected |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in summary_rows:
        lines.append(
            f"| {row['case']} | {row['n']} "
            f"| {row['original_predictive_collision_count']}/{row['original_predictive_completion_count']}/{row['original_predictive_timeout_count']} -> "
            f"{row['corrected_predictive_collision_count']}/{row['corrected_predictive_completion_count']}/{row['corrected_predictive_timeout_count']} "
            f"| {row['original_predictive_mean_finish_completed_s']:.3f} -> {row['corrected_predictive_mean_finish_completed_s']:.3f} s "
            f"| {row['original_selected_pad']} -> {row['corrected_selected_pad']} "
            f"| {row['original_selected_pad_collision_count']}/{row['original_selected_pad_completion_count']}/{row['original_selected_pad_timeout_count']} -> "
            f"{row['corrected_selected_pad_collision_count']}/{row['corrected_selected_pad_completion_count']}/{row['corrected_selected_pad_timeout_count']} "
            f"| {row['original_selected_pad_mean_finish_completed_s']:.3f} -> {row['corrected_selected_pad_mean_finish_completed_s']:.3f} s |"
        )
    lines.extend(
        [
            "",
            "This audit uses the original prototype seed grid and is descriptive. It should not be presented as held-out evidence.",
            "",
        ]
    )
    (RESULTS_DIR / "coordination_state_audit.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )
    print(f"completed in {elapsed:.1f}s", flush=True)


if __name__ == "__main__":
    main()
