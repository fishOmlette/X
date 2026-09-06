from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from enum import Enum
from itertools import combinations

import numpy as np


class RobotState(str, Enum):
    APPROACHING = "approaching"
    WAITING = "waiting"
    CROSSING = "crossing"
    CLEARED = "cleared"


@dataclass(frozen=True)
class CoordinationConfig:
    dt: float = 0.1
    max_time_s: float = 45.0
    robot_count: int = 3
    conflict_distances: tuple[float, ...] = (12.0, 12.5, 13.0)
    clear_distances: tuple[float, ...] = (12.0, 14.0, 16.0)
    nominal_speed: float = 1.2
    max_acceleration: float = 1.0
    zone_radius: float = 0.5
    exit_distance: float = 8.0
    required_headway_s: float = 5.0 / 6.0
    uncertainty_near_s: float = 0.05
    uncertainty_range_s: float = 0.15
    uncertainty_multiplier: float = 1.0
    measurement_noise_s: float = 0.05
    prediction_horizon_s: float = 2.0
    slope_window: int = 8
    speed_floor: float = 0.05
    bias_pattern: tuple[float, ...] = (0.0, 1.0, 2.0)

    @property
    def nominal_zone_occupancy_s(self) -> float:
        return 2.0 * self.zone_radius / self.nominal_speed

    def __post_init__(self) -> None:
        vectors = (self.conflict_distances, self.clear_distances, self.bias_pattern)
        if any(len(values) != self.robot_count for values in vectors):
            raise ValueError("robot_count must match every per-robot tuple")
        if self.dt <= 0 or self.max_time_s <= 0:
            raise ValueError("time step and horizon must be positive")
        if self.nominal_speed <= 0 or self.max_acceleration <= 0:
            raise ValueError("speed and acceleration must be positive")
        if self.required_headway_s < self.nominal_zone_occupancy_s - 1e-12:
            raise ValueError(
                "required_headway_s must be at least the nominal physical zone occupancy"
            )


class PairHistory:
    def __init__(self, window: int):
        if window < 2:
            raise ValueError("window must be at least two samples")
        self.window = window
        self._values: dict[tuple[int, int], deque[tuple[float, float]]] = defaultdict(
            lambda: deque(maxlen=window)
        )

    def observe(self, pair: tuple[int, int], time_s: float, margin_s: float) -> None:
        self._values[tuple(sorted(pair))].append((float(time_s), float(margin_s)))

    def slope(self, pair: tuple[int, int]) -> float:
        values = tuple(self._values.get(tuple(sorted(pair)), ()))
        if len(values) < 2:
            return 0.0
        slopes = [
            (values[right][1] - values[left][1]) / (values[right][0] - values[left][0])
            for left in range(len(values))
            for right in range(left + 1, len(values))
            if values[right][0] != values[left][0]
        ]
        return float(np.median(slopes)) if slopes else 0.0

    def reset(self, pair: tuple[int, int] | None = None) -> int:
        if pair is None:
            count = len(self._values)
            self._values.clear()
            return count
        return int(self._values.pop(tuple(sorted(pair)), None) is not None)

    def counts(self) -> dict[str, int]:
        return {
            f"{left}-{right}": len(values)
            for (left, right), values in self._values.items()
        }


def _crossing_time(
    old_position: float,
    new_position: float,
    boundary: float,
    step_start_s: float,
    dt: float,
) -> float:
    distance = old_position - new_position
    if distance <= 0:
        return step_start_s + dt
    fraction = np.clip((old_position - boundary) / distance, 0.0, 1.0)
    return float(step_start_s + fraction * dt)


def _interval_metrics(
    entry_times: list[float | None],
    exit_times: list[float | None],
    elapsed_s: float,
    required_headway_s: float,
) -> tuple[bool, bool, list[list[int]], list[list[int]], float | None]:
    collision_pairs: list[list[int]] = []
    headway_pairs: list[list[int]] = []
    observed_entries = [value for value in entry_times if value is not None]
    minimum_headway = None

    for left, right in combinations(range(len(entry_times)), 2):
        left_entry = entry_times[left]
        right_entry = entry_times[right]
        if left_entry is None or right_entry is None:
            continue
        headway = abs(left_entry - right_entry)
        minimum_headway = (
            headway if minimum_headway is None else min(minimum_headway, headway)
        )
        if headway < required_headway_s - 1e-12:
            headway_pairs.append([left, right])

        left_exit = exit_times[left] if exit_times[left] is not None else elapsed_s
        right_exit = exit_times[right] if exit_times[right] is not None else elapsed_s
        if max(left_entry, right_entry) < min(left_exit, right_exit) - 1e-12:
            collision_pairs.append([left, right])

    if len(observed_entries) < 2:
        minimum_headway = None
    return (
        bool(collision_pairs),
        bool(headway_pairs),
        collision_pairs,
        headway_pairs,
        minimum_headway,
    )


def run_episode(
    config: CoordinationConfig,
    method: str,
    condition: str,
    seed: int,
    parameter: float = 0.0,
    severity_s: float = 1.0,
    degradation_exponent: float = 1.0,
) -> dict:
    if method not in {"no_intervention", "fixed_pad", "predictive"}:
        raise ValueError(f"unknown method: {method}")
    if condition not in {"conflict", "clear"}:
        raise ValueError(f"unknown condition: {condition}")
    if parameter < 0 or severity_s < 0 or degradation_exponent <= 0:
        raise ValueError(
            "parameter and severity must be nonnegative; exponent must be positive"
        )

    rng = np.random.default_rng(seed)
    initial = np.asarray(
        config.conflict_distances
        if condition == "conflict"
        else config.clear_distances,
        dtype=float,
    )
    position = initial.copy()
    velocity = np.full(config.robot_count, config.nominal_speed, dtype=float)
    state = [RobotState.APPROACHING for _ in range(config.robot_count)]
    blockers = [set() for _ in range(config.robot_count)]
    histories = PairHistory(config.slope_window)
    entry_times: list[float | None] = [None] * config.robot_count
    zone_exit_times: list[float | None] = [None] * config.robot_count
    transitions: list[dict] = []
    yield_events = [0] * config.robot_count
    serialization_breaches = 0
    serialization_order: tuple[int, ...] | None = None
    trigger_time_s = None
    trigger_pair = None
    histories_cleared_at_commit = 0
    elapsed_s = 0.0

    def transition(robot: int, target: RobotState, time_s: float, reason: str) -> None:
        if state[robot] == target:
            return
        transitions.append(
            {
                "time_s": float(time_s),
                "robot": robot,
                "from": state[robot].value,
                "to": target.value,
                "reason": reason,
            }
        )
        state[robot] = target

    def perception() -> tuple[np.ndarray, np.ndarray]:
        remaining = np.maximum(position - config.zone_radius, 0.0)
        arrival = remaining / np.maximum(velocity, config.speed_floor)
        denominator = np.maximum(initial - config.zone_radius, 1e-12)
        fraction = np.clip(remaining / denominator, 0.0, 1.0)
        bias = (
            severity_s
            * np.asarray(config.bias_pattern)
            * fraction**degradation_exponent
        )
        uncertainty = config.uncertainty_near_s + config.uncertainty_range_s * fraction
        return arrival + bias, uncertainty

    step_count = int(np.ceil(config.max_time_s / config.dt))
    for step in range(step_count):
        step_start = step * config.dt

        if serialization_order is not None:
            for robot in serialization_order:
                if state[robot] == RobotState.WAITING and all(
                    state[blocker] == RobotState.CLEARED for blocker in blockers[robot]
                ):
                    transition(
                        robot,
                        RobotState.APPROACHING,
                        step_start,
                        "all blockers cleared",
                    )

        if serialization_order is None and method != "no_intervention":
            candidates = [
                robot
                for robot in range(config.robot_count)
                if state[robot] != RobotState.CLEARED
                and position[robot] > config.zone_radius
            ]
            estimates, uncertainty = perception()
            records = []
            for left, right in combinations(candidates, 2):
                pair = (left, right)
                margin = (
                    abs(estimates[left] - estimates[right])
                    - config.uncertainty_multiplier
                    * (uncertainty[left] + uncertainty[right])
                    - config.required_headway_s
                    + rng.normal(0.0, config.measurement_noise_s)
                )
                histories.observe(pair, step_start, margin)
                slope = histories.slope(pair)
                projected_time = margin / -slope if slope < -1e-6 else np.inf
                records.append((pair, margin, projected_time))

            triggered = []
            for pair, margin, projected_time in records:
                if method == "fixed_pad" and margin <= parameter:
                    triggered.append((margin, pair))
                elif method == "predictive" and (
                    margin <= 0.0 or projected_time <= parameter
                ):
                    triggered.append((projected_time, pair))

            if triggered:
                _, trigger_pair = min(triggered, key=lambda item: (item[0], item[1]))
                trigger_time_s = float(step_start)
                crossing = [
                    robot
                    for robot in range(config.robot_count)
                    if state[robot] == RobotState.CROSSING
                ]
                outside = [
                    robot
                    for robot in range(config.robot_count)
                    if state[robot] != RobotState.CLEARED and robot not in crossing
                ]
                crossing.sort(key=lambda robot: entry_times[robot] or step_start)
                outside.sort(key=lambda robot: (estimates[robot], robot))
                serialization_order = tuple(crossing + outside)
                for rank, robot in enumerate(serialization_order):
                    blockers[robot] = set(serialization_order[:rank])
                    if rank and state[robot] == RobotState.APPROACHING:
                        transition(
                            robot,
                            RobotState.WAITING,
                            step_start,
                            "serialization committed",
                        )
                        yield_events[robot] += 1
                histories_cleared_at_commit = histories.reset()

        target_velocity = np.full(config.robot_count, config.nominal_speed, dtype=float)
        for robot in range(config.robot_count):
            if state[robot] == RobotState.WAITING:
                target_velocity[robot] = 0.0

        old_position = position.copy()
        velocity += np.clip(
            target_velocity - velocity,
            -config.max_acceleration * config.dt,
            config.max_acceleration * config.dt,
        )
        velocity = np.maximum(velocity, 0.0)
        position -= velocity * config.dt
        elapsed_s = min((step + 1) * config.dt, config.max_time_s)

        for robot in range(config.robot_count):
            if entry_times[robot] is None and (
                old_position[robot] > config.zone_radius
                and position[robot] <= config.zone_radius
            ):
                entry_times[robot] = _crossing_time(
                    old_position[robot],
                    position[robot],
                    config.zone_radius,
                    step_start,
                    config.dt,
                )
            if zone_exit_times[robot] is None and (
                old_position[robot] >= -config.zone_radius
                and position[robot] < -config.zone_radius
            ):
                zone_exit_times[robot] = _crossing_time(
                    old_position[robot],
                    position[robot],
                    -config.zone_radius,
                    step_start,
                    config.dt,
                )

            if position[robot] < -config.zone_radius:
                transition(robot, RobotState.CLEARED, elapsed_s, "left shared zone")
            elif position[robot] <= config.zone_radius:
                if state[robot] == RobotState.WAITING and any(
                    state[blocker] != RobotState.CLEARED for blocker in blockers[robot]
                ):
                    serialization_breaches += 1
                    transition(
                        robot,
                        RobotState.CROSSING,
                        elapsed_s,
                        "entered before blockers cleared",
                    )
                elif state[robot] == RobotState.APPROACHING:
                    transition(
                        robot, RobotState.CROSSING, elapsed_s, "entered shared zone"
                    )

        if np.all(position <= -config.exit_distance + 1e-12):
            break

    reached_goal = bool(np.all(position <= -config.exit_distance + 1e-12))
    timed_out = not reached_goal
    collision, headway_violation, collision_pairs, headway_pairs, min_headway = (
        _interval_metrics(
            entry_times,
            zone_exit_times,
            elapsed_s,
            config.required_headway_s,
        )
    )
    successful = reached_goal and not collision and not headway_violation

    return {
        "method": method,
        "condition": condition,
        "seed": int(seed),
        "parameter": float(parameter),
        "severity_s": float(severity_s),
        "degradation_exponent": float(degradation_exponent),
        "reached_goal": reached_goal,
        "collision": collision,
        "headway_violation": headway_violation,
        "timed_out": timed_out,
        "successful": successful,
        "makespan_s": float(elapsed_s) if reached_goal else None,
        "successful_makespan_s": float(elapsed_s) if successful else None,
        "minimum_entry_headway_s": min_headway,
        "entry_times_s": entry_times,
        "zone_exit_times_s": zone_exit_times,
        "collision_pairs": collision_pairs,
        "headway_violation_pairs": headway_pairs,
        "serialization_committed": serialization_order is not None,
        "serialization_order": list(serialization_order)
        if serialization_order
        else None,
        "trigger_time_s": trigger_time_s,
        "trigger_pair": list(trigger_pair) if trigger_pair else None,
        "blockers": [sorted(values) for values in blockers],
        "yield_events_per_robot": yield_events,
        "serialization_breaches": serialization_breaches,
        "final_states": [value.value for value in state],
        "transitions": transitions,
        "pair_history_counts_after_run": histories.counts(),
        "pair_histories_cleared_at_commit": histories_cleared_at_commit,
        "nominal_zone_occupancy_s": config.nominal_zone_occupancy_s,
        "required_headway_s": config.required_headway_s,
    }
