## Setup

- Scenario grid: `3 x 3 x 3 = 27` fixed scenarios.
- Braking rates: `(0.5, 1.0, 2.5)` units/s^2.
- Degradation exponents: `(0.7, 1.0, 1.5)`; hidden-bias severities: `(2.0, 6.0, 10.0)` s.
- Tuning: `20` noise replicates per scenario and candidate. Testing: `60` new noise replicates per scenario and rule.
- Both methods use the grid `0.00..4.00` in `0.25` increments.
- The required gap between entries is the nominal time spent in the zone (0.8333 s). I also check whether interpolated zone-occupancy intervals overlap.

## Chosen settings

- Fixed reactive pad: `1.75` s (540/540 successful tuning runs; mean completion time `29.817` s).
- Predictive horizon: `1.50` s (540/540 successful tuning runs; mean completion time `26.936` s).

## Results on new noise seeds

| Rule | Condition | Successful runs | Collisions | Headway violations | Timeouts | Mean completion time (successful runs) | Serializations |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| no_intervention | conflict | 0/1620 | 1620 | 1620 | 0 | not defined | 0/1620 |
| no_intervention | clear | 1620/1620 | 0 | 0 | 0 | 20.000 s | 0/1620 |
| fixed_pad_tuned | conflict | 1620/1620 | 0 | 0 | 0 | 29.813 s | 1620/1620 |
| fixed_pad_tuned | clear | 1620/1620 | 0 | 0 | 0 | 26.337 s | 1080/1620 |
| predictive_tuned | conflict | 1620/1620 | 0 | 0 | 0 | 27.034 s | 1620/1620 |
| predictive_tuned | clear | 1620/1620 | 0 | 0 | 0 | 20.278 s | 21/1620 |

## Comparing completion times

Both rules succeeded in all `1620` paired conflict runs. The mean time difference (fixed minus predictive) is `2.779` s; the 95% percentile bootstrap interval, grouped over `60` test replicates, is `[2.659, 2.902]` s. Positive values favor prediction. This compares new noise samples on the same 27 scenarios.

## Reading the table

- A run succeeds when every robot reaches the exit without a collision or a headway violation.
- Mean completion time uses successful runs only.
- On clear paths, a serialization means the robots waited unnecessarily.
- Without intervention, repeating a physical scenario gives the same trajectory.
- The test changes measurement noise while keeping the scenario grid fixed.
