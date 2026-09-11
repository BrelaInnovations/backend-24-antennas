"""
Builds a DEFINITIVE list of phase-stable vs phase-unstable antenna pairs
by testing all 64 pairs across several repeat scans, then saves the
result to data/phase_stability_results.json.

This replaces further root-cause chasing with a practical, measured
decision: pairs with genuinely unstable phase get permanently excluded
from run_das(), same mechanism as EXCLUDE_SAME_INDEX_PAIRS. The
remaining ~49 reliable pairs become the array DAS actually trusts.

Usage:
    python build_pair_reliability_list.py "reliability test" 5
(5 repeats recommended for a confident read -- more than the 3 used
so far, since a couple of the earlier "stable" pairs could have gotten
lucky with only 3 samples.)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sys
import json
import numpy as np
from capture_labeled_scan import capture_one_sweep  # direct hardware capture, no server needed

label_base = sys.argv[1] if len(sys.argv) > 1 else "reliability test"
n_runs = int(sys.argv[2]) if len(sys.argv) > 2 else 5
SPREAD_THRESHOLD_DEG = 20.0  # same cutoff used in earlier tests

all_pairs = [f"TX{tx}-RX{rx}" for tx in range(1, 9) for rx in range(1, 9)]
all_runs_phase = {pair: [] for pair in all_pairs}

for run_i in range(1, n_runs + 1):
    label = f"{label_base} {run_i}"
    print(f"Capturing scan {run_i}/{n_runs} (label={label!r}) directly from hardware ...")
    sweep = capture_one_sweep() or {}

    for pair in all_pairs:
        d = sweep.get(pair)
        if not d or not d.get("s21_real"):
            all_runs_phase[pair].append(None)
            continue
        n = len(d["s21_real"])
        mid = n // 2
        re = d["s21_real"][mid]
        im = d["s21_imag"][mid]
        phase_deg = float(np.degrees(np.arctan2(im, re)))
        all_runs_phase[pair].append(phase_deg)

    print(f"Run {run_i}/{n_runs} done.")

stable_pairs = []
unstable_pairs = []
spreads = {}

for pair, phases in all_runs_phase.items():
    valid = [p for p in phases if p is not None]
    if len(valid) < 2:
        unstable_pairs.append(pair)  # missing data -- treat as unreliable
        spreads[pair] = None
        continue
    spread = max(valid) - min(valid)
    spreads[pair] = round(spread, 1)
    if spread >= SPREAD_THRESHOLD_DEG:
        unstable_pairs.append(pair)
    else:
        stable_pairs.append(pair)

result = {
    "n_runs_tested": n_runs,
    "spread_threshold_deg": SPREAD_THRESHOLD_DEG,
    "stable_pairs": sorted(stable_pairs),
    "unstable_pairs": sorted(unstable_pairs),
    "phase_spreads_deg": spreads,
}

import os
os.makedirs("data", exist_ok=True)
with open("data/phase_stability_results.json", "w") as f:
    json.dump(result, f, indent=2)

print()
print(f"Stable pairs:   {len(stable_pairs)} / 64")
print(f"Unstable pairs: {len(unstable_pairs)} / 64")
print()
print("Unstable (to exclude):", ", ".join(sorted(unstable_pairs)))
print()
print("Saved full results to data/phase_stability_results.json")