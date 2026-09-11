"""
Checks whether the saved baseline (data/baseline_full_sweep.json) still
matches a FRESH empty-dome scan taken right now. If it doesn't -- i.e. if
subtracting them produces a strong, coherent peak instead of noise -- the
baseline is stale (drift) and needs to be re-captured before any real
target testing.

Usage:
    python check_baseline_drift.py "empty check fresh"

Run this with the dome EMPTY (nothing inside) when you call it.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sys
import json

import numpy as np
import das_imaging
from capture_labeled_scan import capture_one_sweep  # direct hardware capture, no server needed

NUM_PAIRS_TO_CHECK = 10  # how many strongest pairs to inspect

label = sys.argv[1] if len(sys.argv) > 1 else "empty check fresh"

print(f"Capturing fresh scan (label={label!r}) directly from hardware ...")
fresh_empty = capture_one_sweep()
data = {"label": label}

with open("data/baseline_full_sweep.json") as f:
    saved_baseline = json.load(f)

delta = das_imaging.subtract_baseline(fresh_empty, saved_baseline)

# Rank pairs by mean |delta S21| -- if the saved baseline still matches,
# these should all be small/noisy. If it's stale, some pairs will show a
# clear elevated magnitude, same as a real target would.
ranked = []
for label_pair, d in delta.items():
    if not d.get("s21_real"):
        continue
    mag = np.abs(np.asarray(d["s21_real"]) + 1j * np.asarray(d["s21_imag"]))
    ranked.append((label_pair, mag.mean()))
ranked.sort(key=lambda x: -x[1])

print(f"Label: {data.get('label')}")
print("Comparing FRESH empty scan against saved data/baseline_full_sweep.json")
print()
print(f"Top {NUM_PAIRS_TO_CHECK} pairs by mean |delta S21| (should be small/flat if baseline is still valid):")
print()

peak_delays_ns = []
for pair_label, mean_mag in ranked[:NUM_PAIRS_TO_CHECK]:
    d = delta[pair_label]
    freqs_hz = np.asarray(d["freqs"], dtype=float) * 1e9
    s21_complex = np.asarray(d["s21_real"]) + 1j * np.asarray(d["s21_imag"])
    t, s_t = das_imaging.to_time_domain(freqs_hz, s21_complex, oversample=8)

    mag_t = np.abs(s_t)
    half = len(mag_t) // 2
    peak_idx = np.argmax(mag_t[:half])
    peak_delay_ns = t[peak_idx] * 1e9
    peak_mag = mag_t[peak_idx]
    peak_delays_ns.append(peak_delay_ns)

    print(f"  {pair_label}: mean|delta|={mean_mag:.4e}  time-domain peak={peak_delay_ns:.3f} ns  (mag={peak_mag:.3e})")

print()
print(f"Overall mean |delta S21| across ALL 64 pairs: "
      f"{np.mean([np.abs(np.asarray(d['s21_real']) + 1j*np.asarray(d['s21_imag'])).mean() for d in delta.values() if d.get('s21_real')]):.4e}")
print()
spread = max(peak_delays_ns) - min(peak_delays_ns)
print(f"Peak-time spread across top {NUM_PAIRS_TO_CHECK} pairs: {spread:.3f} ns")
print()
print("INTERPRETATION:")
print("  - If mean|delta| is small (comparable to your VNA noise floor) AND")
print("    peak times look scattered/random pair to pair -> baseline is fine,")
print("    this was just noise.")
print("  - If mean|delta| is elevated and peak times CLUSTER consistently")
print("    (like a real target would) -> baseline has drifted OR there's a")
print("    real fixed structural reflector in the dome. Re-capture the")
print("    baseline now and re-run this to confirm it drops to noise.")