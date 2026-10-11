# Experiment code

I used two small simulators: two robots meeting at a crossing, and three robots sharing a zone. The experiment and plotting scripts use the same simulator code, so the figures and result tables use the same rules for motion, collisions, and completion.

These scripts run with Python, NumPy, and Matplotlib. You do not need ROS 2 or Nav2.

## What each file does

| File | Role |
| --- | --- |
| `single_margin_simulator.py` | Moves the two robots, generates observations, applies triggers, and records what happened. |
| `coordination_simulator.py` | Moves the three robots, tracks pairwise margins, and handles their crossing order. |
| `single_margin_experiment.py` | Tries different fault severities, checks unnecessary yields, and compares predicted and actual margin-expiry times. |
| `stress_tests.py` | Varies the fixed pad, braking rate, rate of margin decline, and fault severity. |
| `heldout_evaluation.py` | Tunes both two-robot rules, tests them on new noise seeds, and saves individual runs and summaries. |
| `coordination_experiment.py` | Tunes and tests the three-robot rules, then saves the runs and comparison. |
| `generate_figures.py` | Draws the three figures and saves their values in `results/figure_data.json`. |

## Single-margin model

Robot A and Robot B approach perpendicular paths through one crossing. A can brake, wait until B clears, and resume. Conflict trials align their nominal arrival times; clear trials measure unnecessary yields. B’s estimated arrival time has range-decaying optimistic bias and range-dependent uncertainty:

```text
g_hat(t) = T_B_hat - T_A_hat
bias(t)  = severity * range_fraction^p
sigma(t) = sigma0 + sigma_range * range_fraction
M(t)     = |g_hat(t)| - k_sigma * sigma(t) - G_safe
```

The exponent `p` controls how the bias disappears as B approaches, and `a_max` limits A’s acceleration and braking. I use two ways to find the latest useful trigger. The analytical calculation asks when A must start braking to stop outside the wider crossing zone. `replay_last_collision_avoiding_trigger` tries trigger times on the simulation grid and returns the latest one that avoids a collision. The two differ because stopping outside the wider zone is more conservative than the collision check.

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

Each robot is `approaching`, `waiting`, `crossing`, or `cleared`. Each pair has its own margin history. At the first trigger, the robots commit to a crossing order. Later robots brake and wait for all earlier robots to clear. That order stays fixed for the rest of the run, which lets me study trigger timing without also changing the recovery plan.

The coordination policies are `no_intervention`, `fixed_pad`, and `predictive`. A fixed rule triggers when a pair margin is at most its pad. A predictive rule triggers when a pair margin is already non-positive or its slope projects a crossing within the chosen horizon. Once triggered, both invoke the same serialization recovery.

Here is what the result fields mean:

- `reached_goal`: all robots reach the configured exit distance.
- `collision`: two interpolated physical zone-occupancy intervals overlap.
- `headway_violation`: two interpolated entry times are separated by less than the required headway.
- `timed_out`: at least one robot fails to reach the exit by the horizon.
- `successful`: all robots reach the exit with neither a collision nor a headway violation.
- `successful_makespan_s`: elapsed time only for successful episodes; it is null for collisions, headway failures, and timeouts.
- `serialization_breaches`: entries made before all recorded blockers clear; the validation requires zero.

## Experiment grids

| Script | Main grid |
| --- | --- |
| `single_margin_experiment.py` | Seeds `0..39`; severities `0, 2, 4, 5, 6, 8, 10`; calibration severities `4, 6, 8`; conflict and clear conditions. |
| `stress_tests.py` | Seeds `0..39`; pads `0, 0.5, 1, 1.5, 2, 3`; braking rates `0.5, 0.75, 1, 1.5, 2, 3, 5`; linear and quadratic degradation; wide severities through `14`. |
| `heldout_evaluation.py` | 45 conflict scenarios: 3 braking rates x 3 exponents x 5 severities; 25 tuning and 150 test noise replicates per scenario; pad and horizon grids `0..4` by `0.25`. |
| `coordination_experiment.py` | 27 scenarios: 3 braking rates x 3 exponents x 3 severities; 20 tuning and 60 test noise replicates per scenario; pad and horizon grids `0..4` by `0.25`; conflict and clear conditions. |

Each combination of split, scenario, and replicate gets its own seed. The rules share that seed for a paired comparison, but tuning and testing use different seeds. Testing changes the noise while keeping the scenario grid fixed.

For two robots, I choose the fastest candidate with zero tuning collisions and break ties toward the smaller parameter. For three robots, a candidate must complete every tuning run successfully and respect the crossing order; I then choose the shortest mean completion time. If none qualifies, the result file records that the fallback selection was used.

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

```powershell
.\.venv\Scripts\python code\generate_figures.py --only boundary
```

## Reading the intervals

I calculate a two-sided 95% Wilson interval for collisions in each scenario and report the largest upper endpoint. That maximum does not give a simultaneous bound across all scenarios. For timing, I use a paired percentile bootstrap, grouping the scenarios by test replicate. I report the interval only when every compared run succeeds, so faster failures do not count as a timing improvement.

## Environment used for the saved runs

The recorded results were generated on Windows 11 build 26200 with Python 3.13.12, NumPy 2.4.4, Matplotlib 3.10.9, and a 13th Gen Intel Core i7-1360P with 12 cores and 16 logical processors. Paper compilation uses MiKTeX 26.5, pdfTeX 4.27, and BibTeX 4.2.

See [../results/README.md](../results/README.md) for the results and the files each script writes.
