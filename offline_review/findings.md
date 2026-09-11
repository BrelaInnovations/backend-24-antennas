# Offline localization findings

**The current scans do not demonstrate reliable 1 cm localization. No rotation, calibration fit or channel tuning was applied.**

## Results using the corresponding available baselines

A uses its preserved baseline. B uses the current baseline that reproduces the saved B heatmaps; original acquisition provenance is not embedded in those scans. A height is corrected to 2.5 cm. B assumes the same support and cube height.

| Scan | Candidate (cm) | Error (cm) | Competing peak / main peak, at least 2 cm away | Antenna omissions moving peak >1 cm |
|---|---|---:|---:|---:|
| single_A1 | [-5.0, 0.5, 0.5] | 7.43 | 0.43 | 1/16 |
| single_A2 | [-5.0, 0.5, 0.5] | 7.43 | 0.49 | 4/16 |
| single_A3 | [-5.0, 0.0, 0.5] | 7.55 | 0.50 | 4/16 |
| single_B1 | [-8.0, 0.0, 0.0] | 6.34 | 0.67 | 7/16 |
| single_B2 | [-7.5, -0.5, 0.0] | 5.72 | 0.96 | 7/16 |
| single_B3 | [-4.0, -5.5, 3.5] | 1.50 | 0.62 | 10/16 |
| single_B4 | [-4.0, -5.5, 3.5] | 1.50 | 0.66 | 9/16 |

The omission results measure dependence on subsets of channels; they are not physical repeatability tests. A strong competitor means a small change in the measured data can potentially select a different peak.

## What is supported

- The reported hemisphere dimensions, arm positions and numbering match the current model.
- A single XY rotation does not explain all A/B results or their depth errors.
- Baseline subtraction leaves structured empty-control responses. A changed baseline can move reconstructed locations substantially.
- Phase stability of the averaged empty scans does not verify antenna phase response or per-pair target-path calibration.
- The current confidence flag is not a validated indicator of localization correctness.
- All seven saved target files passed finite-value, complete 101-point and frequency-grid checks; this cannot recover acquisition details discarded before saving.

## What remains unknown

The files cannot independently establish whether the remaining error is dominated by antenna phase response, multipath, incorrect system-delay offsets, or handling/time drift. Antenna-position confirmation is based on user measurements and labels, not a measured electromagnetic phase-center map.

## One test for the next office visit

Run `python capture_target_toggle.py` from the backend folder when the device is available. Enter the measured center, for example `2 2 2.5` for the same 1 cm cube on the 2 cm support. Keep the support, antennas and cables fixed. Follow the five stages: empty, cube present, empty, cube present, empty. Return the same cube to the same marked position and orientation. The script records three individual sweeps per stage and snapshots the reference files without overwriting the active baseline.

Analyze each target stage against the empty stages before and after it; check whether a repeatable target-induced difference survives both reference choices before attempting a new calibration fit. No acquisition is required today.
