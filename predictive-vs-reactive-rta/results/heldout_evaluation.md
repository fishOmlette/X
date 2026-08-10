# Held-out evaluation

This run separates parameter tuning from testing by independently generated noise replicates. It does not establish real-world safety; it quantifies behavior in the supplied simulator.

## Design

- Tuning replicates: `0..24` (25 per scenario).
- Test replicates: `0..149` (150 per scenario).
- Conflict factorial: 3 recovery rates x 3 degradation exponents x 5 severities = 45 scenarios per replicate.
- Each split/scenario/replicate tuple has a distinct deterministic simulation seed; the same tuple is paired across candidates and methods.
- Both pad and horizon were tuned over `0.00..4.00` in `0.25` increments.
- Selection rule: among candidates with zero tuning collisions, select the one with the lowest mean conflict elapsed time; break ties toward the smaller parameter.
- Exact-scenario collision intervals are two-sided 95% Wilson score intervals. Elapsed-time intervals use a paired percentile bootstrap; the pooled bootstrap resamples replicate indices as conservative clusters across the fixed scenario grid.

## Selected parameters

- Fixed reactive pad: `2.50`.
- Predictive horizon: `2.50` s.
- Original irregular pad-grid selection: `2.50`.

## Held-out pooled results

| Arm | Conflict collisions | Pooled rate | Max pointwise per-scenario Wilson upper (n=150) | Mean successful elapsed time | Successful conflict runs | Clear false yields | Pooled clear rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Fixed pad | 0/6750 | 0.0000 | 0.0250 | 27.690 s | 6750/6750 | 1800/2250 | 0.8000 |
| Predictive horizon | 2/6750 | 0.0003 | 0.0368 | 26.577 s | 6748/6750 | 1358/2250 | 0.6036 |

The raw paired mean elapsed-time difference (fixed minus predictive; positive favors prediction) is `1.113` s. It is descriptive only: elapsed-time inference is suppressed because at least one arm recorded a collision, so no bootstrap interval is reported.

## Files

- `heldout_tuning_grid.csv`: every tuning candidate and its selection metrics.
- `heldout_test_trials.csv`: episode-level held-out results.
- `heldout_seed_map.csv`: deterministic simulation seed for every split/scenario/replicate tuple.
- `heldout_test_summary.csv`: exact-scenario and pooled summaries.
- `heldout_paired_comparisons.csv`: paired scenario and pooled elapsed-time comparisons.
- `heldout_evaluation.json`: configuration, selections, headline results, and runtime.

A zero observed collision count is not a safety proof. The maximum pointwise exact-scenario Wilson upper bound is reported instead of treating the heterogeneous pooled factorial as one binomial sample; it is not a simultaneous confidence bound over all scenarios.
