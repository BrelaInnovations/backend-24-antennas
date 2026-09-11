# naibra_core -- stripped-down localization-only backend

Everything unrelated to "get the correct location" has been removed
(FastAPI/Mongo/GUI-simulation layer, user auth, period tracking, the
legacy line-intersection dot-cloud visualization, etc). What's left:

```
core/
  geometry.py      antenna positions, dome geometry, voxel grid
  calibration.py   per-pair delay table, baseline subtraction, exclusion lists
  timedomain.py    freq-domain S21 -> time-domain (windowed IFFT)
  beamforming.py   run_reconstruction(algo="das"|"das-cf"|"dmas"|"dmas-cf")

hardware.py        serial comms with VNA + TX/RX switches (unchanged)
scan_engine.py      runs a full 64-pair sweep (unchanged)
calibration.py       VNA .cal file loader (unchanged, top-level -- do not
                      confuse with core/calibration.py, which is the
                      per-pair delay/baseline logic)
2-6_cal_with_new_cable.cal   your VNA calibration file

data/
  pair_delay_calibration.json   measured per-pair system delay (64 pairs)
  baseline_full_sweep.json      empty-dome reference for clutter removal
  phase_stability_results.json  measured unstable-pair exclusion list
  switch_role_config.json       TX/RX switch port mapping

capture_labeled_scan.py   capture ONE real scan + record its known true
                           target position into dataset/manifest.json
validate.py                run all 4 algorithms against every labeled
                           scan in dataset/, report real error in cm
```

## Before you start: re-verify your baseline

We found earlier that `data/baseline_full_sweep.json` can drift and stop
matching a fresh empty scan even seconds later -- almost certainly
switch-matrix contact repeatability, not a fixed structure. **Before
building your labeled dataset**, run:
```
python diagnostics/check_baseline_drift.py "predataset check"
```
If `mean|delta S21|` and the peak-time clustering still look elevated,
that's a hardware repeatability issue worth chasing (reseating
connectors, checking the switch matrix) before results from ANY
algorithm will be trustworthy.

Also worth re-running before a serious data-collection session:
```
python diagnostics/measure_system_delay_full.py "cal check"      # refresh per-pair delay table
python diagnostics/check_phase_stability_full.py "stability check"  # refresh unstable-pair list
python diagnostics/build_pair_reliability_list.py                   # regenerate exclusion list
```
`diagnostics/time_domain_check.py` is also still there for the kind of
single-scan, per-pair sanity check we used earlier if a specific result
looks off and you want to trace it back to raw timing.

## Building your labeled dataset

For each target position:
1. Place the target, measure its exact position with a ruler/calipers,
   relative to the dome's base center (origin used throughout --
   apex is at `(0, 0, 8)`).
2. Run:
   ```
   python capture_labeled_scan.py "descriptive label" x_cm y_cm z_cm
   ```
3. Repeat for at least 8-10 different positions -- spread around the
   dome, different depths, some off-center, some near the edge. A
   handful of positions won't tell you much about tolerance; more
   coverage gives a real picture of where the system is accurate and
   where it isn't.

## Running validation

```
python validate.py
```

This runs DAS, DAS-CF, DMAS, and DMAS-CF against every labeled scan,
prints per-scan predicted position + error, then a summary table:
mean/median/max error per algorithm, and what fraction of scans landed
within 1/2/3/5cm of the true position. It also checks `snr_check()`
confidence per algorithm -- an algorithm that's occasionally very
accurate but rarely confident is often less useful in practice than one
that's slightly less accurate but reliably confident, since confidence
is what you'd gate a real detection decision on.

Full per-scan detail is also saved to `validation_report.json`.

## If accuracy still isn't good enough

- Try `--resolution 0.25` for a finer search grid (slower).
- Re-run `measure_system_delay_full.py`-equivalent recalibration if it's
  been a while or cables have moved (stale calibration was the single
  biggest error source we found earlier -- ~170cm down to ~5cm).
- Check whether unstable-phase pairs have changed since
  `phase_stability_results.json` was last generated -- hardware
  contact variance drifts over time.
