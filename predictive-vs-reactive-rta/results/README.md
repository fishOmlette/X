# Experiment results

## Three robots sharing a zone

Prediction reduced mean completion time from `29.813 s` to `27.034 s`, a difference of `2.779 s` (95% paired bootstrap interval `[2.659, 2.902] s`, grouped over 60 test replicates). Both rules completed all `1620/1620` conflict episodes successfully, with no collision, headway violation, timeout, or crossing-order breach.

On clear paths, the fixed rule started an unnecessary serialization in `1080/1620` runs; prediction did so in `21/1620`. Both completed every clear run successfully. Without intervention, all `1620/1620` conflict runs collided and violated the required headway.

Tuning selected a `1.75 s` fixed pad and a `1.50 s` predictive horizon. Both completed `540/540` tuning episodes successfully. The test uses new measurement noise on the same 27 scenarios.

## Two robots at a crossing

Both searches selected `2.50 s`. In 6,750 conflict episodes per rule, the fixed threshold recorded `0` collisions and prediction recorded `2`. On clear paths, unnecessary yields fell from `1800/2250` to `1358/2250`.

Mean completion time among successful conflict runs was `27.690 s` for the fixed rule and `26.577 s` for prediction. The raw paired time difference was `1.113 s`. Since the failure outcomes differ, I keep these times descriptive and do not report a timing interval.

The test uses new noise seeds on the same scenarios. The reported Wilson upper value is the largest upper endpoint from the individual scenario intervals, not a simultaneous bound across the whole grid.

## Where to find things

| Files | Produced by | Contents |
| --- | --- | --- |
| `heldout_evaluation.json`, `heldout_evaluation.md` | `code/heldout_evaluation.py` | Configuration, selections, results, setup notes, and runtime. |
| `heldout_tuning_grid.csv` | `code/heldout_evaluation.py` | Every single-margin tuning candidate and selection metric. |
| `heldout_test_trials.csv` | `code/heldout_evaluation.py` | Episode-level held-out outcomes. |
| `heldout_seed_map.csv` | `code/heldout_evaluation.py` | Deterministic seed for each split/scenario/replicate tuple. |
| `heldout_test_summary.csv` | `code/heldout_evaluation.py` | Exact-scenario and pooled summaries. |
| `heldout_paired_comparisons.csv` | `code/heldout_evaluation.py` | Paired scenario and pooled elapsed-time comparisons. |
| `coordination_validation.json`, `coordination_validation.md` | `code/coordination_experiment.py` | Coordination configuration, selections, outcome definitions, results, setup notes, and runtime. |
| `coordination_validation_tuning.csv` | `code/coordination_experiment.py` | Every coordination tuning candidate and selection metric. |
| `coordination_validation_trials.csv` | `code/coordination_experiment.py` | Episode-level held-out coordination outcomes. |
| `coordination_validation_summary.csv` | `code/coordination_experiment.py` | Test-arm summaries by condition. |
| `figure_data.json` | `code/generate_figures.py` | Values used in the three figures, plus how they were generated. |
| `single_margin_diagnostic.png` | `code/single_margin_experiment.py` | Extra plots of success, collisions, prediction error, and trigger timing. |

## What counts as a successful run

For the single-margin simulator, `successful` means Robot A reached its goal without a recorded collision. `elapsed_time` counts completed updates, including the final one. A robot can reach its goal in a run that also records a collision, so I check success separately from elapsed time.

For the coordination simulator, `successful` means all three robots reached the exit without overlapping physical zone intervals or violating the required entry headway. `successful_makespan_s` is null for collisions, headway failures, and timeouts. `serialization_breaches` separately records a robot entering before all assigned blockers have cleared.

## Rerun the experiments

From the `predictive-vs-reactive-rta` directory, after installing `code/requirements.txt`:

```powershell
.\.venv\Scripts\python code\heldout_evaluation.py
.\.venv\Scripts\python code\coordination_experiment.py
.\.venv\Scripts\python code\generate_figures.py
```

The recorded results were generated on Windows 11 build 26200 with Python 3.13.12, NumPy 2.4.4, Matplotlib 3.10.9, and a 13th Gen Intel Core i7-1360P. Exact wall-clock times are stored in the JSON reports because they vary by machine.
