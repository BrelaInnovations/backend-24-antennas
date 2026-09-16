# Localisation audit — 15 September 2026

## What was reviewed

Current geometry, VNA parsing, switching waits, complex averaging, calibration,
baseline subtraction, DAS/DAS-CF/DMAS/DMAS-CF, today's metaltest1.json and the
three real hardware captures in data/desktop.sqlite3. The other 15 database
scan records are marked simulated and are not physical accuracy evidence.
No hardware or automated test suite was run. Analysis used saved data only.

## Confirmed software defect: app and CLI used different subtraction

The app configured 101 points but server.py capped hardware acquisition at 51.
Its separate subtract_baseline_sweep then subtracted entries by index, truncating
the 101-point baseline without checking frequency. At index 25, scan frequency
is 4 GHz and baseline frequency is 3 GHz; at index 50, they are 6 and 4 GHz.
All three real app captures today have 51 points despite config_snapshot saying
101. Their original reconstructed locations are invalid-comparison diagnostics.

Fix: respect the configured sweep point count and call core.calibration's
frequency-checked subtraction in both app and CLI. No interpolation or automatic
resampling is added to production. Mismatched captures are rejected.

## Today's numerical results

metaltest1: recorded centre (2,-2,2.5) cm; 144 complete, finite 101-point spectra.
No acquisition reference sidecar or settling record exists for this scan.
Available baseline and delay table are from September 11, so temporal matching
cannot be established from supplied files. All four candidates fail confidence.

| Algorithm | Candidate cm | Error cm | Coherence |
|---|---|---:|---:|
| DAS | (-1,-0.5,6.5) | 5.220 | 0.030 |
| DAS-CF | (-7,1.5,3.5) | 9.708 | 0.048 |
| DMAS | (-6.5,1.5,3) | 9.206 | 0.044 |
| DMAS-CF | (2.5,-6,2) | 4.062 | 0.052 |

Scan-minus-baseline norm / baseline norm = 1.263838. Raw complex correlation
magnitude = 0.113801. These measure total signal disagreement, not target-only
response or proof of a particular hardware fault.

For the app captures, a diagnostic selected the exact matching frequencies
from the current 101-point baseline (every second sample, no interpolation):

| Capture UTC | Recorded centre cm | Original DMAS-CF error cm | Frequency-matched diagnostic error cm |
|---|---|---:|---:|
| 11:42:24 | (2,4,2.5) | 6.265 | 10.025 |
| 11:54:45 | (2,-2,2.5) | 1.871 | 4.528 |
| 12:16:49 | (2,-2,2.5) | 1.871 | 4.062 |

These replay results still use current references, not a proven capture-time
snapshot. The worse errors show why the original small errors must not be used
to judge algorithm quality. No target-fitted coordinate shifts were applied.

## Geometry and algorithm assessment

- Radius is 8 cm, six arms, four antenna centres per arm at 3/6/9/12 cm arc
  distance. +Y points toward RX5-8, +X 90 degrees clockwise, +Z above base.
  The calculation matches the user's stated layout. Physical RF port-to-antenna
  continuity and electromagnetic phase centres remain unmeasured.
- Propagation uses TX-to-voxel plus voxel-to-RX distance divided by c for air,
  plus each pair's calibrated system delay. There is no evidence here for
  rotating axes again or imposing a target depth to force the answer.
- The delay table has 144 entries, but is estimated from the largest empty-dome
  time-domain peak. That peak is not independently identified as the direct
  path. Coverage does not prove physical calibration accuracy.
- A scalar time delay compensates a linear phase slope; it does not describe an
  arbitrary frequency-dependent complex antenna/channel response or multipath.
  The present model is much simpler than the potential measured channel.
- Coherence weighting strengthens whichever candidate is more coherent; it
  cannot verify that the candidate is the target. It worsens plain DAS for
  today's metal scan. DMAS-CF is also far from the known position.
- Existing same-index exclusion removes 12 pairs, leaving 132. Its empirical
  justification came from the previous setup; it has not been revalidated on
  this array. No exclusions were tuned to these target coordinates.
- Switch software waits remain 50 ms per command plus 10 ms, much longer than
  the user's stated 1.8 microsecond switching/settling specification. The code
  reads but does not validate switch responses. Actual cable mapping and
  command success cannot be inferred merely from long waits.
- Frequency slots are reordered, but raw VNA indices and individual repeat
  data are not retained in ordinary averaged captures. Complete JSON arrays
  cannot independently prove that acquisition discarded no bad data.

## Other code changes

average_sweeps now refuses missing/error spectra, different repeat pair sets,
nonfinite values, or different frequency grids, instead of hiding failed repeats
or truncating mismatched spectra. The numerical median estimator is unchanged.
Ordinary capture_labeled_scan now saves the same reference provenance used by
settled captures. Existing measurements and prior metadata are not rewritten.

## Next desktop steps

1. Copy updated server.py, scan_engine.py and capture_labeled_scan.py into the
   desktop backend and restart the backend. Keep sweep_points set to 101.
2. Use python capture_target_toggle.py with one metal target at one measured,
   marked centre. Keep the rubber support, cables and antennas fixed. Follow
   empty/target/empty/target/empty, removing only the target. This preserves
   active calibration/baseline and saves three individual sweeps per stage.
3. Share the resulting dataset/target_toggle_* folder. This checks whether a
   repeatable target-induced difference survives the empty references on both
   sides, before another delay fit or algorithm adjustment is justified.
4. If fresh app scanning is needed first, capture a settled empty baseline at
   101 points, then fresh measured targets using the same setup. Do not compare
   today's old 51-point app outputs as if they came from the corrected path.

Remaining: physical localisation has not been solved or validated. The code
fix removes a confirmed corruption path; it does not promise centimetre accuracy.
