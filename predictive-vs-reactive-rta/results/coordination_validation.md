# Coordination held-out evaluation

This experiment uses the one-shot serialization state machine in `code/coordination_simulator.py`. It holds out measurement-noise replicates, not scenario families or robot dynamics.

## Design

- Conflict factorial: `3 x 3 x 3 = 27` fixed scenarios.
- Recovery capabilities: `(0.5, 1.0, 2.5)` units/s^2.
- Degradation exponents: `(0.7, 1.0, 1.5)`; hidden-bias severities: `(2.0, 6.0, 10.0)` s.
- Tuning: `20` independent noise replicates per scenario and candidate. Testing: `60` seed-disjoint replicates per scenario and arm.
- Both methods use the grid `0.00..4.00` in `0.25` increments.
- The required entry headway equals nominal physical zone occupancy (0.8333 s). Collision is measured independently from interpolated occupancy-interval overlap.

## Selection

- Fixed reactive pad: `1.75` s (540/540 successful tuning episodes; mean successful makespan `29.817` s).
- Predictive horizon: `1.50` s (540/540 successful tuning episodes; mean successful makespan `26.936` s).

## Held-out outcomes

| Arm | Condition | Successful | Collisions | Headway violations | Timeouts | Mean successful makespan | Serializations |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| no_intervention | conflict | 0/1620 | 1620 | 1620 | 0 | not defined | 0/1620 |
| no_intervention | clear | 1620/1620 | 0 | 0 | 0 | 20.000 s | 0/1620 |
| fixed_pad_tuned | conflict | 1620/1620 | 0 | 0 | 0 | 29.813 s | 1620/1620 |
| fixed_pad_tuned | clear | 1620/1620 | 0 | 0 | 0 | 26.337 s | 1080/1620 |
| predictive_tuned | conflict | 1620/1620 | 0 | 0 | 0 | 27.034 s | 1620/1620 |
| predictive_tuned | clear | 1620/1620 | 0 | 0 | 0 | 20.278 s | 21/1620 |

## Paired fixed-versus-predictive comparison

All `1620` conflict pairs succeeded. The mean fixed-minus-predictive successful-makespan difference is `2.779` s; the 95% percentile bootstrap interval clustered over `60` test replicates is `[2.659, 2.902]` s. Positive values favor prediction. The interval is conditional on the fixed 27-scenario grid.

## Interpretation limits

- Successful means that every robot reached the exit with neither physical occupancy overlap nor a required-headway violation.
- A makespan is averaged only over successful episodes; it is not assigned to collisions, headway failures, or timeouts.
- Clear-condition serialization counts are unnecessary interventions and are reported explicitly.
- No-intervention repetitions are deterministic duplicates within a physical scenario and are not independent safety evidence.
- Results generalize over simulated measurement noise conditional on this grid, not to unseen geometries or real robots.
