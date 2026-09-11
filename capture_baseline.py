"""
capture_baseline.py -- capture an empty-dome scan and save it as the
baseline used everywhere else: the full complex sweep for DAS baseline
subtraction, AND the raw per-pair dB averages for the severity-score
baseline (compute_weights_from_baseline() in dot_scoring.py).

Make sure the dome is EMPTY before running this.

Usage:
    python capture_baseline.py
"""
import json
import scan_engine
from capture_labeled_scan import capture_one_sweep

print("Capturing empty-dome baseline sweep...")
sweep = capture_one_sweep()

with open("data/baseline_full_sweep.json", "w") as f:
    json.dump(sweep, f)
print("Saved data/baseline_full_sweep.json")

_, raw_values = scan_engine.compute_sensor_weights_from_traces(sweep)
with open("data/baseline_raw_s21.json", "w") as f:
    json.dump(raw_values, f, indent=2)
print("Saved data/baseline_raw_s21.json")