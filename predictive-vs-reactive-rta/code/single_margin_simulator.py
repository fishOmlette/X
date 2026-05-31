from dataclasses import dataclass
from numbers import Integral
from typing import NamedTuple

import numpy as np


@dataclass(frozen=True)
class Cfg:
    dt: float = 0.1
    T_max: float = 40.0
    x0_A: float = -12.0
    goal_A: float = 12.0
    v_nom: float = 1.2
    a_max: float = 1.0
    y0_B: float = -9.0
    vB_conflict: float = 0.9
    vB_clear: float = 2.6
    coll_zone: float = 0.7
    x_zone: float = 0.9
    Gsafe: float = 0.5
    k_sigma: float = 1.0
    sigma0: float = 0.15
    sigma_range: float = 0.45
    meas_noise: float = 0.05
    T_needed: float = 2.0
    slope_window: int = 8

    def __post_init__(self):
        positive = {
            "dt": self.dt,
            "T_max": self.T_max,
            "v_nom": self.v_nom,
            "a_max": self.a_max,
            "vB_conflict": self.vB_conflict,
            "vB_clear": self.vB_clear,
        }
        for name, value in positive.items():
            if not np.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be finite and greater than zero")
        nonnegative = {
            "coll_zone": self.coll_zone,
            "x_zone": self.x_zone,
            "Gsafe": self.Gsafe,
            "k_sigma": self.k_sigma,
            "sigma0": self.sigma0,
            "sigma_range": self.sigma_range,
            "meas_noise": self.meas_noise,
            "T_needed": self.T_needed,
        }
        for name, value in nonnegative.items():
            if not np.isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and nonnegative")
        if not np.isfinite(self.x0_A) or not np.isfinite(self.goal_A):
            raise ValueError("x0_A and goal_A must be finite")
        if self.x0_A >= self.goal_A:
            raise ValueError("x0_A must be less than goal_A")
        if not np.isfinite(self.y0_B) or self.y0_B >= 0:
            raise ValueError("y0_B must be finite and below the crossing")
        if not isinstance(self.slope_window, Integral) or self.slope_window < 2:
            raise ValueError("slope_window must be an integer of at least two")
        if _step_count(self) < 1:
            raise ValueError("T_max must span at least one simulation step")


class Perception(NamedTuple):
    margin: float
    estimated_headway: float
    true_B_time_remaining: float


_METHOD_ALIASES = {
    "B0": "B0",
    "B2": "B2p",
    "B2p": "B2p",
    "fixed_pad": "B2p",
    "fixed-pad": "B2p",
    "P": "P",
}
_CONDITIONS = {"conflict", "clear"}


def _step_count(cfg):
    return int(np.floor(cfg.T_max / cfg.dt + 1e-12))


def _canonical_method(method):
    if not isinstance(method, str) or method not in _METHOD_ALIASES:
        accepted = ", ".join(_METHOD_ALIASES)
        raise ValueError(f"unknown method {method!r}; expected one of: {accepted}")
    return _METHOD_ALIASES[method]


def _validate_run_inputs(condition, seed, severity, fixed_pad, horizon, exponent):
    if condition not in _CONDITIONS:
        raise ValueError(
            f"unknown condition {condition!r}; expected 'conflict' or 'clear'"
        )
    if not isinstance(seed, Integral) or seed < 0:
        raise ValueError("seed must be a nonnegative integer")
    values = {
        "severity": severity,
        "fixed_pad": fixed_pad,
        "horizon": horizon,
        "degradation_exponent": exponent,
    }
    for name, value in values.items():
        if not np.isfinite(value):
            raise ValueError(f"{name} must be finite")
    if severity < 0 or fixed_pad < 0 or horizon < 0 or exponent <= 0:
        raise ValueError(
            "severity, fixed_pad, and horizon must be nonnegative; "
            "degradation_exponent must be positive"
        )


def theil_sen_slope(times, values):
    times = np.asarray(times, dtype=float)
    values = np.asarray(values, dtype=float)
    if times.shape != values.shape:
        raise ValueError("times and values must have the same shape")
    if times.ndim != 1:
        raise ValueError("times and values must be one-dimensional")
    slopes = [
        (values[j] - values[i]) / (times[j] - times[i])
        for i in range(len(times))
        for j in range(i + 1, len(times))
        if times[j] != times[i]
    ]
    return float(np.median(slopes)) if slopes else 0.0


def perceive(cfg, x_A, v_A, y_B, v_B, severity, degradation_exponent, rng):
    time_A = -x_A / max(v_A, 0.05) if x_A < 0 else -1.0
    time_B = -y_B / v_B if y_B < 0 else -1.0
    range_fraction = min(1.0, max(0.0, abs(y_B) / abs(cfg.y0_B)))
    bias = severity * range_fraction**degradation_exponent
    sigma = cfg.sigma0 + cfg.sigma_range * range_fraction
    estimated_time_B = time_B + bias if time_B > 0 else time_B
    estimated_headway = estimated_time_B - time_A
    margin = abs(estimated_headway) - cfg.k_sigma * sigma - cfg.Gsafe
    noisy_margin = margin + rng.normal(0.0, cfg.meas_noise)
    return Perception(float(noisy_margin), float(estimated_headway), float(time_B))


def run_episode(
    cfg,
    method,
    severity,
    condition,
    seed,
    *,
    fixed_pad=0.0,
    horizon=None,
    degradation_exponent=1.0,
):
    canonical_method = _canonical_method(method)
    effective_horizon = cfg.T_needed if horizon is None else horizon
    _validate_run_inputs(
        condition,
        seed,
        severity,
        fixed_pad,
        effective_horizon,
        degradation_exponent,
    )

    rng = np.random.default_rng(int(seed))
    v_B = cfg.vB_conflict if condition == "conflict" else cfg.vB_clear
    x_A, v_A, y_B = cfg.x0_A, cfg.v_nom, cfg.y0_B
    yielded = False
    resumed = False
    collision = False
    t_yield = None
    margins = []
    times = []
    steps_executed = 0

    for step in range(_step_count(cfg)):
        time = step * cfg.dt
        observation = perceive(
            cfg,
            x_A,
            v_A,
            y_B,
            v_B,
            severity,
            degradation_exponent,
            rng,
        )
        margins.append(observation.margin)
        times.append(time)

        if not yielded and observation.true_B_time_remaining > 0:
            if canonical_method == "B0":
                should_yield = abs(observation.estimated_headway) < cfg.Gsafe
            elif canonical_method == "B2p":
                should_yield = observation.margin <= fixed_pad
            else:
                window = cfg.slope_window
                slope = (
                    theil_sen_slope(times[-window:], margins[-window:])
                    if len(margins) >= 2
                    else 0.0
                )
                time_to_zero = observation.margin / -slope if slope < -1e-3 else np.inf
                should_yield = (
                    time_to_zero <= effective_horizon or observation.margin <= 0
                )
            if should_yield:
                yielded = True
                t_yield = time

        if yielded and not resumed:
            target_velocity = 0.0
            if y_B > cfg.x_zone:
                resumed = True
        else:
            target_velocity = cfg.v_nom

        velocity_change = np.clip(
            target_velocity - v_A,
            -cfg.a_max * cfg.dt,
            cfg.a_max * cfg.dt,
        )
        v_A = max(0.0, v_A + velocity_change)
        x_A += v_A * cfg.dt
        y_B += v_B * cfg.dt
        collision = collision or (abs(x_A) < cfg.coll_zone and abs(y_B) < cfg.coll_zone)
        steps_executed = step + 1
        if x_A >= cfg.goal_A:
            break

    reached_goal = bool(x_A >= cfg.goal_A)
    collision = bool(collision)
    timed_out = not reached_goal and steps_executed == _step_count(cfg)
    successful = reached_goal and not collision
    return {
        "method": canonical_method,
        "severity": float(severity),
        "condition": condition,
        "seed": int(seed),
        "fixed_pad": float(fixed_pad),
        "horizon": float(effective_horizon),
        "degradation_exponent": float(degradation_exponent),
        "yielded": yielded,
        "t_yield": t_yield,
        "reached_goal": reached_goal,
        "collision": collision,
        "timed_out": timed_out,
        "successful": successful,
        "steps_executed": steps_executed,
        "elapsed_time": steps_executed * cfg.dt,
    }


def conservative_crossing_zone_stopping_deadline(cfg):
    stopping_distance = cfg.v_nom**2 / (2.0 * cfg.a_max)
    available_distance = -cfg.x_zone - cfg.x0_A
    deadline = (available_distance - stopping_distance) / cfg.v_nom
    return None if deadline < 0 else float(deadline)


def _forced_trigger_collision(cfg, condition, trigger_step):
    v_B = cfg.vB_conflict if condition == "conflict" else cfg.vB_clear
    x_A, v_A, y_B = cfg.x0_A, cfg.v_nom, cfg.y0_B
    yielded = False
    resumed = False
    collision = False

    for step in range(_step_count(cfg)):
        if not yielded and step >= trigger_step and y_B < 0:
            yielded = True

        if yielded and not resumed:
            target_velocity = 0.0
            if y_B > cfg.x_zone:
                resumed = True
        else:
            target_velocity = cfg.v_nom

        velocity_change = np.clip(
            target_velocity - v_A,
            -cfg.a_max * cfg.dt,
            cfg.a_max * cfg.dt,
        )
        v_A = max(0.0, v_A + velocity_change)
        x_A += v_A * cfg.dt
        y_B += v_B * cfg.dt
        collision = collision or (abs(x_A) < cfg.coll_zone and abs(y_B) < cfg.coll_zone)
        if x_A >= cfg.goal_A:
            break
    return collision


def replay_last_collision_avoiding_trigger(cfg, condition="conflict"):
    if condition not in _CONDITIONS:
        raise ValueError(
            f"unknown condition {condition!r}; expected 'conflict' or 'clear'"
        )
    v_B = cfg.vB_conflict if condition == "conflict" else cfg.vB_clear
    approaching_steps = [
        step for step in range(_step_count(cfg)) if cfg.y0_B + v_B * step * cfg.dt < 0
    ]
    safe_steps = [
        step
        for step in approaching_steps
        if not _forced_trigger_collision(cfg, condition, step)
    ]
    return None if not safe_steps else max(safe_steps) * cfg.dt
