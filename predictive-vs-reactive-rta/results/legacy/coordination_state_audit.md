# Coordination state-transition audit

The original state keeps yielding=True after release, so that robot is permanently excluded from active pair selection even while it is still approaching the shared zone.

The audit makes a released robot eligible for pair selection again and starts a fresh yield cycle if it is selected later. No existing simulator file was changed.

`C/K/T` denotes collision count, collision-free completion count, and timeout count. Finish time is averaged only over collision-free completed episodes.

| Case | n | P C/K/T old -> corrected | P completed finish old -> corrected | Selected pad old -> corrected | Fixed-pad C/K/T old -> corrected | Fixed-pad completed finish old -> corrected |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| homogeneous_narrow | 60 | 3/57/0 -> 0/60/0 | 29.530 -> 40.872 s | 0.5 -> 0.0 | 0/60/0 -> 0/60/0 | 29.600 -> 40.632 s |
| homogeneous_wide | 180 | 5/175/0 -> 0/180/0 | 29.477 -> 40.411 s | 0.5 -> 0.0 | 0/180/0 -> 0/180/0 | 29.600 -> 40.149 s |
| heterogeneous_narrow | 60 | 0/60/0 -> 0/60/0 | 35.550 -> 40.193 s | 0.0 -> 0.0 | 0/60/0 -> 0/60/0 | 35.550 -> 35.550 s |
| heterogeneous_wide | 180 | 0/180/0 -> 0/180/0 | 33.583 -> 36.121 s | 0.0 -> 0.0 | 0/180/0 -> 0/180/0 | 33.583 -> 33.583 s |
| heterogeneous_wide_shape_0.3 | 180 | 0/180/0 -> 0/180/0 | 33.583 -> 33.646 s | 0.0 -> 0.0 | 0/180/0 -> 0/180/0 | 33.583 -> 33.583 s |
| heterogeneous_wide_shape_2.0 | 180 | 0/180/0 -> 0/180/0 | 33.583 -> 39.472 s | 0.0 -> 0.0 | 0/180/0 -> 0/180/0 | 33.583 -> 33.583 s |

This audit uses the original prototype seed grid and is descriptive. It should not be presented as held-out evidence.
