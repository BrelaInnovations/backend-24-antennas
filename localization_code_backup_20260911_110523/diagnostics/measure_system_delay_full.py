"""
Extends measure_system_delay.py from a 7-pair sample to all 64 pairs, and
goes one step further: instead of just reporting one global mean/std, it
decomposes the per-pair offset into a per-TX-antenna and per-RX-antenna
component via least squares.

Why: if all 16 feed cables (8 TX + 8 RX) were truly identical length, every
pair's offset would equal the same constant, and the earlier 7-pair test
would have already nailed it (std was 0.759ns, ~11% of the mean -- decent,
not perfect). The remaining spread could come from a few antennas having
a slightly different cable/connector/switch-port delay than the rest.

Model: offset(TXi, RXj) = base_delay + tx_residual[i] + rx_residual[j]
Solved by least squares over all 64 measured offsets. tx_residual/rx_residual
close to 0 for most antennas, with one or two standing out, would tell us
exactly which physical antenna/cable/switch-port to inspect.

Usage:
    python measure_system_delay_full.py "empty check"

Run against an EMPTY-DEVICE scan -- we want the raw direct-coupling peak
(line-of-sight leakage between TX and RX antennas), not a baseline-
subtracted target signal.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sys
import json
import numpy as np

sys.path.insert(0, ".")
import das_imaging as das
from capture_labeled_scan import capture_one_sweep  # direct hardware capture, no server needed

label = sys.argv[1] if len(sys.argv) > 1 else "empty check"

print(f"Capturing scan (label={label!r}) directly from hardware ...")
sweep = capture_one_sweep()

positions = das.physical_antenna_positions()
velocity = das.SPEED_OF_LIGHT_CM_PER_S  # air, current testing phase

tx_ids = [f"TX{i}" for i in range(1, 9)]
rx_ids = [f"RX{i}" for i in range(1, 9)]

rows = []       # (tx_idx, rx_idx, offset_ns)
pair_offsets = {}

for i, tx_id in enumerate(tx_ids):
    for j, rx_id in enumerate(rx_ids):
        label_pair = f"{tx_id}-{rx_id}"
        d = sweep.get(label_pair)
        if not d or not d.get("s21_real"):
            continue

        tx_pos = np.array(positions[tx_id])
        rx_pos = np.array(positions[rx_id])
        dist = np.linalg.norm(tx_pos - rx_pos)
        expected_s = dist / velocity

        freqs_hz = np.asarray(d["freqs"], dtype=float) * 1e9
        s21 = np.asarray(d["s21_real"]) + 1j * np.asarray(d["s21_imag"])
        t, s_t = das.to_time_domain(freqs_hz, s21, oversample=8)

        mask = t <= 30e-9
        mag = np.abs(s_t[mask])
        peak_idx = np.argmax(mag)
        observed_s = t[mask][peak_idx]

        offset_ns = (observed_s - expected_s) * 1e9
        rows.append((i, j, offset_ns))
        pair_offsets[label_pair] = offset_ns

if not rows:
    print("No pairs found in sweep_plot_data -- check the API response.")
    sys.exit(1)

print(f"Measured offsets for {len(rows)} / 64 pairs.")
all_offsets = np.array([r[2] for r in rows])
print(f"Global mean offset: {all_offsets.mean():.3f} ns  (std: {all_offsets.std():.3f} ns)")
print()

# Save the raw per-pair table now, regardless of how well the per-antenna
# model below fits -- this is the actual measurement and the safest thing
# to feed into run_das() as a direct lookup, since it captures whatever
# the switch matrix is really doing (additive per-antenna or not).
calib_path = "data/pair_delay_calibration.json"
with open(calib_path, "w") as f:
    json.dump({k: v * 1e-9 for k, v in pair_offsets.items()}, f, indent=2)
print(f"Saved per-pair delay table ({len(pair_offsets)} pairs) to {calib_path}")
print()

# --- Least squares decomposition: offset = base + tx_res[i] + rx_res[j] ---
# Design matrix: one column per TX antenna (8), one per RX antenna (8), plus
# a constant. Fix tx_res[0] = 0 as reference (else system is under-determined
# -- adding a constant to all tx_res and subtracting it from all rx_res gives
# the same fit).
n = len(rows)
num_tx, num_rx = len(tx_ids), len(rx_ids)
num_coeffs = 1 + (num_tx - 1) + num_rx
A = np.zeros((n, num_coeffs))
b = np.zeros(n)
for row_idx, (i, j, off) in enumerate(rows):
    A[row_idx, 0] = 1.0  # base delay
    if i > 0:
        A[row_idx, 1 + (i - 1)] = 1.0  # tx_res[i], tx_res[0] fixed at 0
    A[row_idx, 1 + (num_tx - 1) + j] = 1.0  # rx_res[j]
    b[row_idx] = off

# Fixing tx_res[0]=0 removes the TX-side gauge freedom, but there's a
# second one left: shifting every rx_res[j] by +d and base by -d gives an
# identical fit. Left alone, lstsq's minimum-norm solution splits that
# arbitrarily (verified against synthetic data -- recovered rx_res comes
# out shifted by a constant, ~0.5ns off in testing, not matching physical
# reality). Pin it down with a heavily-weighted constraint row forcing
# mean(rx_res) = 0, so "base" absorbs the true shared component and
# rx_res becomes genuine per-RX-antenna deviation from that shared mean.
constraint_row = np.zeros((1, num_coeffs))
constraint_row[0, num_tx:num_tx + num_rx] = 1.0
constraint_weight = 1e4
A = np.vstack([A, constraint_row * constraint_weight])
b = np.concatenate([b, [0.0]])

coeffs, *_ = np.linalg.lstsq(A, b, rcond=None)
base = coeffs[0]
tx_res = np.concatenate(([0.0], coeffs[1:num_tx]))
rx_res = coeffs[num_tx:num_tx + num_rx]

print(f"Fitted base delay: {base:.3f} ns")
print()
print("Per-TX-antenna residual (ns, relative to TX1):")
for i, tx_id in enumerate(tx_ids):
    flag = "  <-- outlier" if abs(tx_res[i]) > 1.0 else ""
    print(f"  {tx_id}: {tx_res[i]:+.3f}{flag}")
print()
print("Per-RX-antenna residual (ns, relative to fitted base):")
for j, rx_id in enumerate(rx_ids):
    flag = "  <-- outlier" if abs(rx_res[j]) > 1.0 else ""
    print(f"  {rx_id}: {rx_res[j]:+.3f}{flag}")

# Residual after fit -- how much unexplained spread is left (only over the
# real n measurements, not the synthetic zero-mean constraint row appended
# above for the gauge fix).
predicted = A[:n] @ coeffs
resid = b[:n] - predicted
print()
print(f"Residual after per-antenna fit: mean={resid.mean():.3f} ns, std={resid.std():.3f} ns")
if resid.std() < 0.3:
    print("LOW residual std -- per-antenna model explains the spread well.")
    print("Fix: apply base_delay + tx_res[tx] + rx_res[rx] per pair in run_das(),")
    print("instead of one single global SYSTEM_DELAY_S constant.")
else:
    print("Residual still fairly high -- per-antenna cable length isn't the")
    print("full story; there may be per-pair (not per-antenna) variation, e.g.")
    print("individual switch contacts, worth checking pairs with largest")
    print("leftover residual specifically.")
    worst = np.argsort(-np.abs(resid))[:5]
    print("Worst-fit pairs:")
    for idx in worst:
        i, j, off = rows[idx]
        print(f"  {tx_ids[i]}-{rx_ids[j]}: measured={off:.3f} ns, "
              f"predicted={predicted[idx]:.3f} ns, residual={resid[idx]:+.3f} ns")