## Setup

- Tuning replicates: `0..24` (25 per scenario).
- Test replicates: `0..149` (150 per scenario).
- Scenario grid: 3 recovery rates x 3 degradation exponents x 5 severities = 45 scenarios per replicate.
- Each split/scenario/replicate combination gets a distinct seed, shared across rules and candidates for a paired comparison.
- Both pad and horizon were tuned over `0.00..4.00` in `0.25` increments.
- Choose the fastest candidate with zero tuning collisions; break ties toward the smaller parameter.
- I use two-sided 95% Wilson intervals for collisions in each scenario. Timing intervals use a paired percentile bootstrap, grouping scenarios by test replicate for the overall comparison.

## Chosen settings

- Fixed reactive pad: `2.50`.
- Predictive horizon: `2.50` s.
- Pad selected from the original grid: `2.50`.

## Results across the test grid

| Rule | Conflict collisions | Collision rate | Largest scenario Wilson upper endpoint (n=150) | Mean time (successful runs) | Successful conflict runs | Unnecessary clear-path yields | Clear-path yield rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Fixed pad | 0/6750 | 0.0000 | 0.0250 | 27.690 s | 6750/6750 | 1800/2250 | 0.8000 |
| Predictive horizon | 2/6750 | 0.0003 | 0.0368 | 26.577 s | 6748/6750 | 1358/2250 | 0.6036 |

The raw paired mean time difference (fixed minus predictive; positive favors prediction) is `1.113` s. I leave out the bootstrap interval because at least one rule recorded a collision, so the timing difference is descriptive.

## Files

- `heldout_tuning_grid.csv`: every tuning candidate and its selection metrics.
- `heldout_test_trials.csv`: episode-level held-out results.
- `heldout_seed_map.csv`: deterministic simulation seed for every split/scenario/replicate tuple.
- `heldout_test_summary.csv`: exact-scenario and pooled summaries.
- `heldout_paired_comparisons.csv`: paired scenario and pooled elapsed-time comparisons.
- `heldout_evaluation.json`: configuration, selections, headline results, and runtime.

The Wilson value is the largest upper endpoint from the individual scenario intervals. It is not a simultaneous bound across all scenarios.
