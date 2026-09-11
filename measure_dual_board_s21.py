"""
measure_dual_board_s21.py -- measure S21 through BOTH switch boards at
once (TX channel N -> antenna path -> RX channel M), i.e. the exact same
signal path a real scan uses for one antenna pair. Unlike
measure_component.py (single board, S11 only, or S21 with port2 on a
plain reference jumper), this selects a channel on EACH board and
measures true two-port S21 straight through both switch matrices.

This is the test to run after single-board S11 isolation (RFC, cables,
antenna chain) has all come back clean of the 1.78ns feature -- it
checks whether the artifact only appears when both boards are in the
signal path together (e.g. cross-talk between the two boards, a shared
ground/power artifact that only shows up under full 2-port operation,
or something in the TX->RX path that no single-board S11 test can see).

Usage:
    python measure_dual_board_s21.py <label> --tx-channel N --rx-channel M

WIRING:
    VNA port 1 -> TX switch board's COMMON port (RFC)
    VNA port 2 -> RX switch board's COMMON port (RFC)
    Each switch board's selected channel port -> whatever is normally
    connected there for a real scan (antenna, or leave as your test
    calls for -- this script doesn't care what's on the channel side,
    it just selects the channel and measures port1->port2).

Saves dataset/dualboard_<label>.json (same format as
component_<label>.json: freqs/s11_real/s11_imag/s21_real/s21_imag) and
prints the S21 time-domain peak, with a specific check at 1.78ns.
"""
import sys
import os
import json
import argparse
from pathlib import Path
from time import sleep

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import hardware
from core import timedomain

START_HZ = int(2.0e9)
STOP_HZ = int(6.0e9)
POINTS = 101

KNOWN_ARTIFACT_NS = 1.78
ARTIFACT_WINDOW_NS = 0.15  # +/- window to check around the known artifact time


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("label")
    parser.add_argument("--tx-channel", type=int, required=True,
                         help="channel (1-8) to select on the TX switch board")
    parser.add_argument("--rx-channel", type=int, required=True,
                         help="channel (1-8) to select on the RX switch board")
    args = parser.parse_args()

    print(f"Measuring: {args.label}")
    print("VNA port 1 -> TX switch board's COMMON port (RFC).")
    print("VNA port 2 -> RX switch board's COMMON port (RFC).")
    print(f"Selecting TX channel {args.tx_channel}, RX channel {args.rx_channel}.")
    input("Press Enter once wired and ready...")

    detected = hardware.auto_detect_devices()
    if not detected["vna_port"]:
        raise RuntimeError(f"Could not auto-detect VNA: {detected}")

    tx_port, rx_port, _cfg = hardware.resolve_tx_rx_ports(detected["switch_ports"])
    if not tx_port or not rx_port:
        raise RuntimeError(
            f"Could not auto-detect BOTH switch boards (need both plugged in "
            f"over USB): {detected}"
        )

    tx_ser, _b1, _e1 = hardware.open_serial_connection_with_fallbacks(
        tx_port, "Auto", "TX")
    if not tx_ser:
        raise RuntimeError("Failed to open TX board serial connection")

    rx_ser, _b2, _e2 = hardware.open_serial_connection_with_fallbacks(
        rx_port, "Auto", "RX")
    if not rx_ser:
        tx_ser.close()
        raise RuntimeError("Failed to open RX board serial connection")

    hardware.send_switch_command(tx_ser, hardware.format_switch_command(args.tx_channel))
    sleep(0.05)
    hardware.send_switch_command(rx_ser, hardware.format_switch_command(args.rx_channel))
    sleep(0.05)
    print(f"Selected TX channel {args.tx_channel}, RX channel {args.rx_channel}.")

    vna_ser, _b, _e = hardware.open_serial_connection_with_fallbacks(
        detected["vna_port"], "Auto", "VNA")
    if not vna_ser:
        tx_ser.close()
        rx_ser.close()
        raise RuntimeError("Failed to open VNA serial connection")

    try:
        hardware.set_vna_sweep(vna_ser, START_HZ, STOP_HZ, POINTS)
        sleep(0.1)
        hardware.clear_vna_fifo(vna_ser)
        raw = hardware.read_vna_data(vna_ser, POINTS)
        points_data = hardware.parse_vna_data(raw, POINTS)
    finally:
        vna_ser.close()
        hardware.send_switch_command(tx_ser, "OFF;")
        hardware.send_switch_command(rx_ser, "OFF;")
        tx_ser.close()
        rx_ser.close()

    step = (STOP_HZ - START_HZ) / (POINTS - 1)
    freqs_ghz, s11, s21 = [], [], []
    for p in points_data:
        freq_hz = START_HZ + p["freq_idx"] * step
        freqs_ghz.append(freq_hz / 1e9)
        fwd = p["fwd"]
        s11_val = p["refl"] / fwd if abs(fwd) > 0 else 0j
        s21_val = p["thru"] / fwd if abs(fwd) > 0 else 0j
        s11.append(s11_val)
        s21.append(s21_val)

    s11 = np.array(s11)
    s21 = np.array(s21)
    freqs_hz = np.array(freqs_ghz) * 1e9

    s21_db = 20 * np.log10(np.clip(np.abs(s21), 1e-12, None))
    print(f"\n--- Insertion loss (S21) for '{args.label}' ---")
    print(f"  mean: {s21_db.mean():.2f} dB   worst: {s21_db.min():.2f} dB   best: {s21_db.max():.2f} dB")

    t, s21_t = timedomain.to_time_domain(freqs_hz, s21, oversample=8)
    mask = t <= 30e-9
    mag = np.abs(s21_t[mask])
    tt_ns = t[mask] * 1e9

    peak_idx = int(np.argmax(mag))
    peak_t_ns = float(tt_ns[peak_idx])
    peak_mag = float(mag[peak_idx])
    print(f"  time-domain S21 global peak: t={peak_t_ns:.3f}ns, magnitude={peak_mag:.5f}")

    win_mask = np.abs(tt_ns - KNOWN_ARTIFACT_NS) <= ARTIFACT_WINDOW_NS
    if win_mask.any():
        win_mag = mag[win_mask]
        win_tt = tt_ns[win_mask]
        win_peak_idx = int(np.argmax(win_mag))
        print(f"  in +/-{ARTIFACT_WINDOW_NS}ns window around known {KNOWN_ARTIFACT_NS}ns artifact:"
              f" local max t={win_tt[win_peak_idx]:.3f}ns, magnitude={win_mag[win_peak_idx]:.5f}"
              f"  ({win_mag[win_peak_idx] / peak_mag * 100:.1f}% of global peak)")
    print(f"  (compare this against the known 1.78ns TX/RX single-board S11 artifact --")
    print(f"   look for whether a DISTINCT local bump exists there, not just the ramp/tail")
    print(f"   of a bigger peak elsewhere)")

    out = {
        "freqs": freqs_ghz,
        "s11_real": s11.real.tolist(),
        "s11_imag": s11.imag.tolist(),
        "s21_real": s21.real.tolist(),
        "s21_imag": s21.imag.tolist(),
    }
    out_path = Path("dataset") / f"dualboard_{args.label}.json"
    out_path.parent.mkdir(exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(out, f)
    print(f"\nSaved {out_path}")


if __name__ == "__main__":
    main()