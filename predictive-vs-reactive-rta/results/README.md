# Generated results

This directory contains machine-generated evidence for the manuscript. Regenerate these files with the scripts named below; do not edit numerical values by hand.

## Headline outcomes

### Single-margin held-out evaluation

Both searches selected `2.50`: seconds of fixed reactive pad and seconds of predictive horizon. Across 6,750 held-out conflict episodes per arm, the fixed rule recorded `0` collisions and the tuned predictive rule recorded `2`. Because collision outcomes differ, the fixed-minus-predictive elapsed-time difference is descriptive and its inferential interval is suppressed. Clear-condition false yields were `1800/2250` for the fixed rule and `1358/2250` for prediction.

Mean successful conflict elapsed time was `27.690 s` for the fixed rule and `26.577 s` for prediction. Their raw all-pairs elapsed-time difference of `1.113 s` is not interpreted inferentially because the safety outcomes differ.

The test split holds out noise replicates, not simulator families or scenarios. The maximum reported scenario Wilson upper value is the maximum of pointwise 95% intervals; it is not a simultaneous worst-case safety bound. Zero observed collisions are not proof of safety.

### Three-robot held-out validation

The fixed-pad search selected `1.75 s`; the predictive search selected a `1.50 s` horizon. Both candidates had `540/540` successful tuning episodes. On held-out conflict tests, both completed `1620/1620` episodes successfully with no collision, headway violation, timeout, or serialization breach. Mean successful makespan was `29.813 s` for the fixed rule and `27.034 s` for prediction. The paired fixed-minus-predictive difference was `2.779 s`, with a 95% percentile bootstrap interval of `[2.659, 2.902] s` clustered over 60 test replicates.

The no-intervention conflict control collided and violated headway in all `1620/1620` episodes, confirming that the geometry requires coordination. In the clear condition, the fixed policy serialized `1080/1620` episodes and the predictive policy serialized `21/1620`; both still completed all episodes successfully. These results generalize over simulated measurement noise conditional on the fixed 27-scenario grid, not to unseen geometries or real robots.

## File catalogue

| Files | Produced by | Contents |
| --- | --- | --- |
| `heldout_evaluation.json`, `heldout_evaluation.md` | `code/heldout_evaluation.py` | Configuration, selections, headline results, limitations, and runtime. |
| `heldout_tuning_grid.csv` | `code/heldout_evaluation.py` | Every single-margin tuning candidate and selection metric. |
| `heldout_test_trials.csv` | `code/heldout_evaluation.py` | Episode-level held-out outcomes. |
| `heldout_seed_map.csv` | `code/heldout_evaluation.py` | Deterministic seed for each split/scenario/replicate tuple. |
| `heldout_test_summary.csv` | `code/heldout_evaluation.py` | Exact-scenario and pooled summaries. |
| `heldout_paired_comparisons.csv` | `code/heldout_evaluation.py` | Paired scenario and pooled elapsed-time comparisons. |
| `coordination_validation.json`, `coordination_validation.md` | `code/coordination_experiment.py` | Coordination configuration, selections, outcome definitions, headline results, limitations, and runtime. |
| `coordination_validation_tuning.csv` | `code/coordination_experiment.py` | Every coordination tuning candidate and selection metric. |
| `coordination_validation_trials.csv` | `code/coordination_experiment.py` | Episode-level held-out coordination outcomes. |
| `coordination_validation_summary.csv` | `code/coordination_experiment.py` | Test-arm summaries by condition. |
| `figure_data.json` | `code/generate_figures.py` | Values and provenance used in the four paper figures. |
| `single_margin_diagnostic.png` | `code/single_margin_experiment.py` | Exploratory success, collision, calibration, and trigger-deadline diagnostic; not used in the paper. |

Files under `legacy/` document diagnosis of the superseded coordination implementation. They are development records, not primary paper evidence and not inputs to the final figures.

## Outcome definitions

For the single-margin simulator, `successful` means Robot A reached its goal without a recorded collision. `elapsed_time` counts completed updates, including the final one. A collision and completion can both occur in the same episode, so elapsed-time comparisons are not treated as safety-adjusted performance comparisons.

For the coordination simulator, `successful` means all three robots reached the exit without overlapping physical zone intervals or violating the required entry headway. `successful_makespan_s` is null for collisions, headway failures, and timeouts. `serialization_breaches` separately records a robot entering before all assigned blockers have cleared.

## Reproduce

From the repository root, after installing `code/requirements.txt`:

```powershell
.\.venv\Scripts\python code\heldout_evaluation.py
.\.venv\Scripts\python code\coordination_experiment.py
.\.venv\Scripts\python code\generate_figures.py
```

The release environment is Windows 11 build 26200, Python 3.13.12, NumPy 2.4.4, Matplotlib 3.10.9, and a 13th Gen Intel Core i7-1360P. Exact wall-clock times are stored in the JSON reports because they vary by machine.
