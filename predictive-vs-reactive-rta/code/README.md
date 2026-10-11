# Experiment code

The codebase contains two canonical simulators: a two-robot single-margin model and a three-robot shared-zone model. Experiment, validation, and plotting scripts import those simulators so that paper figures and tabulated results use the same dynamics and outcome definitions.

No ROS 2 or Nav2 installation is needed; experiments on a full navigation stack are future work.

## Architecture

| File | Role |
| --- | --- |
| `single_margin_simulator.py` | Canonical two-robot dynamics, observation model, trigger policies, outcome fields, and deadline helpers. |
| `coordination_simulator.py` | Canonical three-robot state machine, pair histories, serialization, physical zone intervals, and outcome fields. |
| `single_margin_experiment.py` | Exploratory dose response, clear-condition specificity, prediction calibration, and diagnostic plot. |
| `stress_tests.py` | Exploratory fixed-pad, braking-rate, degradation-shape, and wide-severity sweeps. |
| `heldout_evaluation.py` | Seed-disjoint tuning/test evaluation for the single-margin policies; writes episode and aggregate records. |
| `coordination_experiment.py` | Broad, seed-disjoint coordination tuning/test evaluation; writes episode and aggregate records. |
| `generate_figures.py` | Regenerates the three paper figures and `results/figure_data.json`. |
| `legacy/` | Superseded coordination prototype and its diagnostic audit; retained for provenance, not used by the paper pipeline. |

The design explanation lives here rather than in long source comments. Comments in the Python files are reserved for local invariants or non-obvious implementation choices.

## Single-margin model

Robot A and Robot B approach perpendicular paths through one crossing. A can brake, wait until B clears, and resume. Conflict trials align their nominal arrival times; clear trials measure unnecessary yields. B’s estimated arrival time has range-decaying optimistic bias and range-dependent uncertainty:

```text
g_hat(t) = T_B_hat - T_A_hat
bias(t)  = severity * range_fraction^p
sigma(t) = sigma0 + sigma_range * range_fraction
M(t)     = |g_hat(t)| - k_sigma * sigma(t) - G_safe
```

The exponent `p` controls the degradation shape, and `a_max` limits A’s acceleration and braking. The conservative analytical deadline is the last continuous-time instant at which immediate constant braking from nominal speed stops A outside the wider crossing zone. It is a kinematic proxy, not the simulator’s exact collision boundary. `replay_last_collision_avoiding_trigger` separately reports the latest tested discrete trigger that avoids a collision for a specified condition.

### Policies

| Name | Trigger |
| --- | --- |
| `B0` | Yield when the estimated absolute headway is below `G_safe`. |
| `B2` | Uncertainty-aware reactive rule at `M <= 0`; implemented as `B2p` with a zero pad. |
| `B2p` / `fixed_pad` | Yield at `M <= pad`. |
| `P` | Estimate the recent Theil–Sen margin slope; yield when projected time to `M <= 0` is within the horizon, or when `M <= 0` already. |

To avoid dividing by a fitted slope near zero, the single-margin implementation projects only when the fitted slope is below `-1e-3` margin units/s. The coordination implementation uses `-1e-6`. Otherwise prediction falls back to the current-margin test `M <= 0`.

### Episode outcomes

- `reached_goal`: A reaches its configured goal before the simulation horizon.
- `collision`: at least one completed update places both robots inside the configured collision zone.
- `timed_out`: A has not reached its goal after every configured step.
- `successful`: A reaches the goal and no collision was recorded.
- `elapsed_time`: completed updates multiplied by `dt`; it includes the final update.
- `yielded` and `t_yield`: whether and when A first committed to yielding.

## Three-robot coordination model

Three robots approach one shared zone. The conflict distances `(12.0, 12.5, 13.0)` produce overlapping nominal zone occupancy; the clear distances `(12.0, 14.0, 16.0)` do not. The required entry headway equals the nominal physical occupancy time, `5/6 s` at the default speed.

Each robot is in one of four explicit states: `approaching`, `waiting`, `crossing`, or `cleared`. Before a trigger, pair-specific margin histories are maintained independently. A trigger commits once to an estimated crossing order. Every later robot records the earlier robots as blockers, brakes, and resumes only after all of its blockers have cleared. The one-shot commitment prevents stale pair histories and repeated-yield ambiguity from changing the policy mid-recovery.

The coordination policies are `no_intervention`, `fixed_pad`, and `predictive`. A fixed rule triggers when a pair margin is at most its pad. A predictive rule triggers when a pair margin is already non-positive or its slope projects a crossing within the chosen horizon. Once triggered, both invoke the same serialization recovery.

Coordination outcomes are stricter than mere completion:

- `reached_goal`: all robots reach the configured exit distance.
- `collision`: two interpolated physical zone-occupancy intervals overlap.
- `headway_violation`: two interpolated entry times are separated by less than the required headway.
- `timed_out`: at least one robot fails to reach the exit by the horizon.
- `successful`: all robots reach the exit with neither a collision nor a headway violation.
- `successful_makespan_s`: elapsed time only for successful episodes; it is null for collisions, headway failures, and timeouts.
- `serialization_breaches`: entries made before all recorded blockers clear; the validation requires zero.

## Experiment grids

The compact scripts are exploratory. Their sample means describe the evaluated grid and must not be called population estimates or formal safety guarantees.

| Script | Main grid |
| --- | --- |
| `single_margin_experiment.py` | Seeds `0..39`; severities `0, 2, 4, 5, 6, 8, 10`; calibration severities `4, 6, 8`; conflict and clear conditions. |
| `stress_tests.py` | Seeds `0..39`; pads `0, 0.5, 1, 1.5, 2, 3`; braking rates `0.5, 0.75, 1, 1.5, 2, 3, 5`; linear and quadratic degradation; wide severities through `14`. |
| `heldout_evaluation.py` | 45 conflict scenarios: 3 braking rates x 3 exponents x 5 severities; 25 tuning and 150 test noise replicates per scenario; pad and horizon grids `0..4` by `0.25`. |
| `coordination_experiment.py` | 27 scenarios: 3 braking rates x 3 exponents x 3 severities; 20 tuning and 60 test noise replicates per scenario; pad and horizon grids `0..4` by `0.25`; conflict and clear conditions. |

For the held-out evaluations, every split/scenario/replicate tuple maps to a distinct deterministic seed, and paired methods reuse that tuple’s seed. Tuning and test noise replicates do not overlap. The scenario grids themselves are fixed rather than sampled from a population.

The single-margin selection rule first restricts to candidates with zero tuning collisions, then minimizes mean conflict elapsed time, breaking ties toward the smaller parameter. The coordination rule first restricts to candidates with 100% successful tuning episodes and no serialization breach, then minimizes successful-only makespan; the result file explicitly records the fallback if no candidate qualifies.

## Run order

From the `predictive-vs-reactive-rta` directory:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r code\requirements.txt
.\.venv\Scripts\python -m unittest discover -s tests -v

.\.venv\Scripts\python code\single_margin_experiment.py
.\.venv\Scripts\python code\stress_tests.py
.\.venv\Scripts\python code\heldout_evaluation.py
.\.venv\Scripts\python code\coordination_experiment.py
.\.venv\Scripts\python code\generate_figures.py
```

`single_margin_experiment.py` writes its exploratory four-panel diagnostic to `results/single_margin_diagnostic.png`. `heldout_evaluation.py` and `coordination_experiment.py` overwrite their named files under `results/`; Tables II and III of the paper report values from `results/heldout_evaluation.json` and `results/coordination_validation.json`. `generate_figures.py` reruns the exploratory sweeps it plots and writes `fig_mechanism.pdf`, `fig_dose.pdf`, and `fig_boundary.pdf` to `figures/`, together with the plotted values in `results/figure_data.json`. To regenerate one figure only, use, for example:

```powershell
.\.venv\Scripts\python code\generate_figures.py --only boundary
```

## Statistical scope

Exact-scenario collision intervals are two-sided 95% Wilson score intervals. Reported maximum Wilson upper bounds are maxima of pointwise scenario intervals, not simultaneous bounds. Paired elapsed-time or makespan intervals use a percentile bootstrap clustered by test replicate and are reported only when both arms satisfy the comparison’s success criterion. A zero observed collision count is not a safety proof.

## Tested environment

The recorded results were generated on Windows 11 build 26200 with Python 3.13.12, NumPy 2.4.4, Matplotlib 3.10.9, and a 13th Gen Intel Core i7-1360P with 12 cores and 16 logical processors. Paper compilation uses MiKTeX 26.5, pdfTeX 4.27, and BibTeX 4.2.

See [../results/README.md](../results/README.md) for generated-file provenance and headline outcomes.
