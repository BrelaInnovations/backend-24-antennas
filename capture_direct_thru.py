"""
capture_direct_thru.py -- isolation test #1: VNA port1 cabled STRAIGHT to
port2, one cable, nothing else in the loop. No DPDT, no TX switch board,
no RX switch board, no antennas.

This is the cheapest, most diagnostic test for the 1.78ns / ~140x
artifact that's shown up identically across all 64 antenna pairs in
every capture so far (empty dome, real targets, after arm rotation,
after DPDT averaging -- it never moved, never changed magnitude). Since
it's identical across pairs that don't share any single antenna, cable,
or switch leg, the culprit has to be something shared by every
measurement: the VNA itself (or the .cal file's reference plane), the
DPDT relay, or one of the two switch boards.

This test isolates the FIRST of those. Physically:
    VNA port 1 ----[single cable]---- VNA port 2
No DPDT, no switch boards, no antennas anywhere in the path.

Then:
    - If the 1.78ns peak still shows up here -> it's the VNA reference
      plane or the .cal file, not any piece of switch/relay hardware.
      Every board you own is innocent.
    - If it's NOT here -> the artifact is introduced downstream, by the
      DPDT and/or one of the switch boards. Run the DPDT-bypass test
      next (VNA straight into each switch board's common port) to
      narrow it down further.

Usage:
    python capture_direct_thru.py
"""
import json

import hardware
import calibration as vna_calibration
from scan_engine import process_sweep_data

CALIBRATION_FILE = "2-6_cal_with_new_cable.cal"
START_HZ = int(2000.0 * 1e6)
STOP_HZ = int(6000.0 * 1e6)
POINTS = 101
NUM_SWEEP_AVERAGES = 10
OUT_FILE = "dataset/direct_thru_test.json"


def capture_one_direct_sweep(vna_ser, cal):
    hardware.set_vna_sweep(vna_ser, START_HZ, STOP_HZ, POINTS)
    from time import sleep
    sleep(0.1)
    hardware.clear_vna_fifo(vna_ser)
    raw = hardware.read_vna_data(vna_ser, POINTS)
    sweep_data = hardware.parse_vna_data(raw, POINTS)
    freqs, s21_db, s21_complex_list = process_sweep_data(
        sweep_data, START_HZ, STOP_HZ, POINTS, calibration=cal)
    return {
        "freqs": freqs,
        "s21": s21_db,
        "s21_real": [c.real for c in s21_complex_list],
        "s21_imag": [c.imag for c in s21_complex_list],
    }


def check_artifact_peak(entry, label="direct_thru"):
    """Same logic used throughout this debugging session: convert to
    time domain, find the dominant peak, report its delay and magnitude
    so it's directly comparable to the 1.780ns / ~0.0045 seen on every
    full-system capture so far."""
    import numpy as np
    from core import timedomain

    s21 = np.asarray(entry["s21_real"]) + 1j * np.asarray(entry["s21_imag"])
    freqs_hz = np.asarray(entry["freqs"], dtype=float) * 1e9
    t, s_t = timedomain.to_time_domain(freqs_hz, s21, oversample=8)
    mag = np.abs(s_t)
    window_mask = t * 1e9 < 20
    t_win = t[window_mask]
    mag_win = mag[window_mask]
    peak_idx = np.argmax(mag_win)
    print(f"{label}: dominant peak at t={t_win[peak_idx]*1e9:.3f}ns  mag={mag_win[peak_idx]:.5f}")
    print(f"  (compare to every prior full-system capture: t=1.780ns, mag~0.0045)")
    return t_win[peak_idx], mag_win[peak_idx]


def main():
    print("=== Direct thru test: VNA port1 -> port2, single cable, ===")
    print("=== nothing else connected (no DPDT, no switch boards)  ===")
    print()
    print("Confirm before continuing:")
    print("  1. VNA port 1 is cabled directly to VNA port 2")
    print("  2. DPDT relay is NOT in this path")
    print("  3. Neither switch board is in this path")
    input("Press Enter once confirmed, or Ctrl+C to abort...")

    detected = hardware.auto_detect_devices()
    if not detected["vna_port"]:
        raise RuntimeError(f"Could not auto-detect VNA: {detected}")

    vna_ser = None
    try:
        vna_ser, _b, _e = hardware.open_serial_connection_with_fallbacks(
            detected["vna_port"], "Auto", "VNA")
        if not vna_ser:
            raise RuntimeError("Failed to open VNA serial connection")

        cal = None
        import pathlib
        if pathlib.Path(CALIBRATION_FILE).exists():
            cal = vna_calibration.get_calibration(CALIBRATION_FILE)
        else:
            print(f"WARNING: {CALIBRATION_FILE} not found -- running uncorrected")

        print("Capturing (3 averaged sweeps)...")
        sweeps = []
        for i in range(NUM_SWEEP_AVERAGES):
            print(f"  sweep {i+1}/{NUM_SWEEP_AVERAGES} ...")
            sweeps.append(capture_one_direct_sweep(vna_ser, cal))

        # simple average across the 3 sweeps (same real/imag mean approach
        # used elsewhere in this codebase)
        import numpy as np
        avg = {"freqs": sweeps[0]["freqs"]}
        real_stack = np.array([s["s21_real"] for s in sweeps])
        imag_stack = np.array([s["s21_imag"] for s in sweeps])
        avg["s21_real"] = real_stack.mean(axis=0).tolist()
        avg["s21_imag"] = imag_stack.mean(axis=0).tolist()
        avg["s21"] = sweeps[0]["s21"]

    finally:
        if vna_ser:
            try:
                vna_ser.close()
            except Exception:
                pass

    import os
    os.makedirs("dataset", exist_ok=True)
    with open(OUT_FILE, "w") as f:
        json.dump(avg, f)
    print(f"Saved {OUT_FILE}")
    print()

    check_artifact_peak(avg)


if __name__ == "__main__":
    main()