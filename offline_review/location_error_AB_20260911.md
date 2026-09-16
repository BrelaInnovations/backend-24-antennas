# A/B location-error investigation, 2026-09-11

Offline saved-data analysis only. No hardware capture or automated test suite run.
Axes: +Y toward RX5-8, +X 90 degrees clockwise viewed from above, +Z upward.
Radius 8 cm. Each capture was analysed against its own saved baseline and delay table.

| Scan | True centre cm | DMAS-CF candidate cm | 3D error cm | Coherence |
|---|---|---|---:|---:|
| 24_A | (-3, 2, 2.5) | (0.5, 2.5, 7.5) | 6.124 | 0.044 |
| 24_B | (0, 0, 2.5) | (-1, -2.5, 7) | 5.244 | 0.059 |

Both captures passed short-term settling. That does not establish repeatable
empty references across handling, or prove the target is localised.

## Reference sensitivity

A and B used different saved baselines but the same delay table.
Norm(B_empty - A_empty) / norm(A_empty) = 0.655817.
Norm(A_scan - A_empty) / norm(A_empty) = 0.297410.
Norm(B_scan - B_empty) / norm(B_empty) = 0.236340.
These are full complex S21 norms, not percentages of target-only signal.
The denominators differ. Handling/support changes and hardware/time drift
cannot be separated with these files alone.

Changing A to B's baseline moves its DMAS-CF candidate to (5,1.5,6),
with 8.746 cm error. Changing B to A's baseline gives (2.5,-1.5,4),
with 3.279 cm error. The smaller error is not validation of the wrong reference.
Empty B minus empty A alone creates a structured peak at (-5.5,0.5,2.5),
coherence 0.042, peak-to-mean 37.3, with no inserted target comparison.

The heatmap script previously used current references when replaying historical
scans. It now verifies and uses the target capture's saved baseline/delay table.
This makes replays consistent; it does not remove the measured location error.

## Timing and coherence

Across the 132 selected pairs, the strongest differential peak within the
0..1.2 ns model propagation interval lies a median absolute 0.386 ns (A)
and 0.267 ns (B) away from the predicted true-target arrival. Only 19.7%
and 21.2% lie within 0.1 ns. These peaks may be clutter/multipath and are
not independently identified target echoes, so these differences are not
measured calibration errors.

At the true target voxel, coherence is only 0.010 (A) and 0.012 (B).
Its DMAS-CF intensity is 0.66% and 0.76% of the strongest voxel respectively.
Coherence weighting favors a wrong high-depth candidate. No known-depth
constraint, target-fitted shift, channel deletion or arbitrary rotation was applied.
Changing to plain DAS/DMAS does not solve both scans: own-reference DAS errors
are 3.937/5.025 cm and DMAS errors are 2.872/5.244 cm for A/B.

## Next discriminating measurement

Run `python capture_target_toggle.py` on the desktop. Use the same target,
support and marked centre throughout. The guided sequence is empty, target,
empty, target, empty, with three individual sweeps per stage. Keep cables,
antennas and rubber support fixed; remove only the target. It preserves active
references. Compare each insertion against the empty stages on both sides
before trying another calibration fit. This distinguishes repeatable target
response from changes introduced by handling/time more directly than another
single target capture or a finer voxel grid.
