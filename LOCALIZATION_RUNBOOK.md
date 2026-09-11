# 24-antenna localisation: desktop commands

Work in PowerShell from `C:\Users\prasr\Downloads\backend-24-antennas`.
User-confirmed axes: +Y toward RX5-8, +X 90 degrees clockwise viewed from above,
+Z above the base. Diameter 16 cm, four antennas per arm at 3/6/9/12 cm
arc distance from the apex. Use these axes when measuring target centres.

## First: inspect existing files, without hardware

```powershell
python diagnostics\localization_readiness.py
```

On the supplied files this should report 64/144 calibrated pairs and exit
with code 2. This is an expected blocker, not a failed installation.
The five scans and empty baseline have 144 spectra each; the old delay
table cannot reconstruct them correctly. Original measurements are preserved.

## Refresh references with the dome empty

Keep the rubber support, antennas and cables fixed. Close other applications
using the VNA/switch serial ports. Run each command separately and proceed
only when it completes successfully.

```powershell
python check_hardware.py
python diagnostics\measure_system_delay_full.py "24 antenna empty calibration"
python capture_settled_baseline.py
python diagnostics\localization_readiness.py
```

The delay command must report 144/144 pairs. It saves the raw empty sweep,
previous delay table and geometry under `data/calibration_sessions/`.
It estimates system delay from the strongest empty-device peak. That peak
can contain multipath: complete coverage does not prove delay accuracy.
Settled captures save reference snapshots under `data/capture_sessions/`.
The existing baseline is also snapshotted before replacement.

## Capture fresh measured targets

Place the same target on the same rubber support. Measure its centre.
Use a new label for every repeat; existing labels overwrite their scan.
For example, ONLY if the measured centre is actually (2, 2, 2.5) cm:

```powershell
python capture_settled_labeled_scan.py "session2_B1" 2 2 2.5
python capture_settled_labeled_scan.py "session2_B2" 2 2 2.5
```

Repeat at the other measured positions and at more than one height.
Do not assign the example coordinates without measuring them. Then run:

```powershell
python diagnostics\localization_readiness.py --reconstruct --resolution 0.5
```

Send `localization_readiness.json` and the new scan/provenance files.
The report uses CURRENT references and records their hashes. Historical
scans may not match new references; do not combine their errors with a new
session as proof of improvement. Image confidence is not a validated
probability that the position is correct. A finer grid is not proof of
better physical accuracy; use 0.25 cm only after the coarse result tracks
target movement reliably.

No hardware capture or automated test suite was run by the assistant for
these changes. Python source was checked for syntax; desktop verification
remains necessary.
