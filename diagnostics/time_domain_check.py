"""
Lower-level DAS diagnostic: instead of the full 3D grid search, this looks
at ONE antenna pair at a time. For each of the pairs known to carry real
signal (from check_scan.py's raw-dB diagnostic), it:

  1. Subtracts baseline (same as run_das does internally)
  2. Converts that pair's spectrum to a time-domain response (same
     to_time_domain() run_das uses)
  3. Finds where the peak actually is in time
  4. Compares that against where the peak SHOULD be, given your measured
     true object position -- computed directly from antenna geometry,
     independent of the full grid search / argmax logic.

If the observed peak delay is close to the expected delay -> the per-pair
delay math is sound, and the bug is in how run_das COMBINES the 64 pairs
(the coherent-sum / grid-search step).

If the observed peak is nowhere near the expected delay, even for a single
pair -- the bug is upstream of that, in to_time_domain() or the delay
formula itself.

EDIT TRUE_POSITION_CM BELOW to your actual measured object position before
running (origin = dome base center, z = height above base, matches how you
described your measurements earlier).

Usage:
    python time_domain_check.py "metal repeat 1"
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sys
import json

import numpy as np
import das_imaging
from capture_labeled_scan import capture_one_sweep  # direct hardware capture, no server needed

# ---- EDIT THIS to your actual measured position for this scan ----
TRUE_POSITION_CM = (2.0, 1.0, 3.0)
# ---------------------------------------------------------------

NUM_PAIRS_TO_CHECK = 6  # how many top-signal pairs to inspect

label = sys.argv[1] if len(sys.argv) > 1 else "check"

print(f"Capturing scan (label={label!r}) directly from hardware ...")
sweep = capture_one_sweep()
data = {"label": label}

with open("data/baseline_full_sweep.json") as f:
    baseline = json.load(f)

delta = das_imaging.subtract_baseline(sweep, baseline)

# Rank pairs by mean |delta S21| across frequency, same idea as the raw-dB
# ranking check_scan.py does, just on full complex data instead of dB.
ranked = []
for label_pair, d in delta.items():
    if not d.get("s21_real"):
        continue
    mag = np.abs(np.asarray(d["s21_real"]) + 1j * np.asarray(d["s21_imag"]))
    ranked.append((label_pair, mag.mean()))
ranked.sort(key=lambda x: -x[1])

positions = das_imaging.physical_antenna_positions()
velocity = das_imaging.tissue_velocity_cm_per_s(1.0)  # air, matches current bench-test phase
true_pos = np.array(TRUE_POSITION_CM)

print(f"Label: {data.get('label')}")
print(f"Assumed true position (cm): {TRUE_POSITION_CM}")
print(f"Velocity used (air, permittivity=1): {velocity:.4e} cm/s")
print()

for pair_label, _mag in ranked[:NUM_PAIRS_TO_CHECK]:
    tx_name, rx_name = pair_label.split("-")
    tx_pos = np.array(positions[tx_name])
    rx_pos = np.array(positions[rx_name])

    # Expected delay if the reflector is exactly at TRUE_POSITION_CM
    expected_dist = np.linalg.norm(true_pos - tx_pos) + np.linalg.norm(true_pos - rx_pos)
    expected_delay_ns = (expected_dist / velocity) * 1e9

    # Direct TX-RX coupling delay (shortest possible path, sanity floor)
    direct_dist = np.linalg.norm(tx_pos - rx_pos)
    direct_delay_ns = (direct_dist / velocity) * 1e9

    d = delta[pair_label]
    freqs_hz = np.asarray(d["freqs"], dtype=float) * 1e9
    s21_complex = np.asarray(d["s21_real"]) + 1j * np.asarray(d["s21_imag"])
    t, s_t = das_imaging.to_time_domain(freqs_hz, s21_complex, oversample=8)

    mag_t = np.abs(s_t)
    # Only look at the first half of the IFFT output (time-domain from a
    # real bandlimited spectrum is periodic/mirrored -- the physically
    # meaningful early part is what we want).
    half = len(mag_t) // 2
    peak_idx = np.argmax(mag_t[:half])
    peak_delay_ns = t[peak_idx] * 1e9
    peak_mag = mag_t[peak_idx]

    # Also report the top-3 peaks (local maxima) in case of multipath/smearing
    order = np.argsort(-mag_t[:half])[:3]
    top3 = sorted(t[order] * 1e9)

    print(f"{pair_label}:")
    print(f"  TX pos={tuple(round(v,2) for v in tx_pos)}  RX pos={tuple(round(v,2) for v in rx_pos)}")
    print(f"  Direct TX-RX delay (floor):     {direct_delay_ns:.3f} ns")
    print(f"  Expected delay @ true position: {expected_delay_ns:.3f} ns")
    print(f"  OBSERVED peak delay:            {peak_delay_ns:.3f} ns  (mag={peak_mag:.3e})")
    print(f"  Top-3 peak times (ns):          {[round(x,3) for x in top3]}")
    diff_ns = peak_delay_ns - expected_delay_ns
    print(f"  Difference from expected:       {diff_ns:+.3f} ns  ({diff_ns * velocity / 1e9:+.2f} cm equiv.)")
    print()