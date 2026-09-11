"""
compare_inner_sweeps.py

Diagnostic only.

Runs capture_one_sweep() while exposing the THREE individual sweeps
inside each capture, instead of immediately taking their median.

Purpose:
    Determine whether phase instability is already present between
    consecutive hardware sweeps.

We compare:
    TX6-RX3  -> previously highly unstable
    TX4-RX8  -> previously very stable

NO hardware configuration is changed.
"""

import sys
import os
import json
from pathlib import Path

import numpy as np

sys.path.insert(
    0,
    os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )
)

import hardware
import scan_engine
import calibration as vna_calibration


NUM_ANTENNAS = 8
START_HZ = int(2000.0 * 1e6)
STOP_HZ = int(6000.0 * 1e6)
POINTS = 101

NUM_INNER_SWEEPS = 1

CALIBRATION_FILE = Path("2-6_cal_with_new_cable.cal")

PAIRS_TO_CHECK = [
    "TX6-RX3",   # unstable
    "TX4-RX8",   # stable
]


def capture_three_individual_sweeps():
    """
    Same hardware setup and acquisition sequence as capture_one_sweep(),
    but returns all three individual sweeps instead of averaging them.
    """

    detected = hardware.auto_detect_devices()

    tx_port, rx_port, _cfg = hardware.resolve_tx_rx_ports(
        detected["switch_ports"]
    )

    if (
        not detected["vna_port"]
        or not tx_port
        or not rx_port
    ):
        raise RuntimeError(
            f"Could not auto-detect all devices: {detected}"
        )

    vna_ser = None
    tx_ser = None
    rx_ser = None

    try:

        vna_ser, _b1, _e1 = (
            hardware.open_serial_connection_with_fallbacks(
                detected["vna_port"],
                "Auto",
                "VNA",
            )
        )

        tx_ser, _b2, _e2 = (
            hardware.open_serial_connection_with_fallbacks(
                tx_port,
                "Auto",
                "TX",
            )
        )

        rx_ser, _b3, _e3 = (
            hardware.open_serial_connection_with_fallbacks(
                rx_port,
                "Auto",
                "RX",
            )
        )

        if not (vna_ser and tx_ser and rx_ser):
            raise RuntimeError(
                "Failed to open one or more serial connections"
            )

        cal = None

        if CALIBRATION_FILE.exists():
            cal = vna_calibration.get_calibration(
                str(CALIBRATION_FILE)
            )
        else:
            print(
                f"WARNING: {CALIBRATION_FILE} not found -- "
                "running uncorrected"
            )

        individual_sweeps = []

        for i in range(NUM_INNER_SWEEPS):

            print(
                f"    inner sweep {i + 1}/{NUM_INNER_SWEEPS}..."
            )

            sweep = scan_engine.run_full_sweep(
                vna_ser,
                tx_ser,
                rx_ser,
                START_HZ,
                STOP_HZ,
                num_antennas=NUM_ANTENNAS,
                points=POINTS,
                calibration=cal,
            )

            individual_sweeps.append(sweep)

        return individual_sweeps

    finally:

        for ser in (
            vna_ser,
            tx_ser,
            rx_ser,
        ):
            try:
                if ser:
                    ser.close()
            except Exception:
                pass


def phase_difference_deg(a, b):
    """
    Circular phase difference between two complex spectra.
    Returns absolute difference in degrees in [0, 180].
    """

    phase_a = np.angle(a)
    phase_b = np.angle(b)

    diff = np.angle(
        np.exp(1j * (phase_b - phase_a))
    )

    return np.degrees(np.abs(diff))


def analyze_pair(sweeps, pair):

    spectra = []

    freqs = None

    for sweep in sweeps:

        data = sweep.get(pair)

        if not data:
            continue

        re = data.get("s21_real")
        im = data.get("s21_imag")

        if (
            not re
            or not im
            or len(re) != len(im)
        ):
            continue

        spectrum = (
            np.asarray(re)
            + 1j * np.asarray(im)
        )

        spectra.append(spectrum)

        if freqs is None:
            freqs = np.asarray(
                data.get("freqs", [])
            )

    if len(spectra) < 2:
        print(
            f"Not enough valid spectra for {pair}"
        )
        return None

    # ------------------------------------------------------------
    # Compare consecutive inner sweeps
    # ------------------------------------------------------------

    pairwise_diffs = []

    for i in range(len(spectra) - 1):

        diff = phase_difference_deg(
            spectra[i],
            spectra[i + 1],
        )

        pairwise_diffs.append(diff)

    pairwise_diffs = np.asarray(
        pairwise_diffs
    )

    # Average across the three inner sweeps.
    mean_diff_per_freq = np.mean(
        pairwise_diffs,
        axis=0,
    )

    # Mean S21 magnitude across inner sweeps.
    magnitudes = np.mean(
        np.asarray([
            np.abs(s)
            for s in spectra
        ]),
        axis=0,
    )

    n = min(
        len(freqs),
        len(mean_diff_per_freq),
        len(magnitudes),
    )

    freqs = freqs[:n]
    mean_diff_per_freq = (
        mean_diff_per_freq[:n]
    )
    magnitudes = magnitudes[:n]

    print()
    print("=" * 70)
    print(pair)
    print("=" * 70)

    print(
        f"Mean phase difference across "
        f"inner sweeps: "
        f"{np.mean(mean_diff_per_freq):.2f} deg"
    )

    print(
        f"Maximum phase difference: "
        f"{np.max(mean_diff_per_freq):.2f} deg"
    )

    print()
    print(
        f"{'Freq(GHz)':>10s} "
        f"{'|S21|':>12s} "
        f"{'InnerPhaseDiff':>17s}"
    )

    print("-" * 45)

    # Print every 5th frequency bin to keep output manageable.
    for i in range(0, n, 5):

        print(
            f"{freqs[i]:10.3f} "
            f"{magnitudes[i]:12.5e} "
            f"{mean_diff_per_freq[i]:17.2f}"
        )

    # ------------------------------------------------------------
    # Find worst frequencies
    # ------------------------------------------------------------

    worst_indices = np.argsort(
        mean_diff_per_freq
    )[-10:][::-1]

    print()
    print("Worst 10 frequency bins:")

    print(
        f"{'Freq(GHz)':>10s} "
        f"{'|S21|':>12s} "
        f"{'PhaseDiff':>12s}"
    )

    print("-" * 38)

    for i in worst_indices:

        print(
            f"{freqs[i]:10.3f} "
            f"{magnitudes[i]:12.5e} "
            f"{mean_diff_per_freq[i]:12.2f}"
        )

    return {
        "freqs_ghz": freqs.tolist(),
        "mean_abs_s21": magnitudes.tolist(),
        "mean_inner_phase_difference_deg":
            mean_diff_per_freq.tolist(),
    }


def main():

    print()
    print(
        "Running individual-inner-sweep diagnostic."
    )
    print()
    print(
        "IMPORTANT:"
    )
    print(
        "  Device must remain EMPTY."
    )
    print(
        "  Do NOT touch/reconnect anything."
    )
    print()

    print(
        f"Each capture performs "
        f"{NUM_INNER_SWEEPS} individual sweeps."
    )

    print(
        "Comparing TX6-RX3 and TX4-RX8."
    )

    print()

    sweeps = (
        capture_three_individual_sweeps()
    )

    results = {}

    for pair in PAIRS_TO_CHECK:

        results[pair] = analyze_pair(
            sweeps,
            pair,
        )

    out_path = Path(
        "data/inner_sweep_phase_diagnostic.json"
    )

    out_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    out_path.write_text(
        json.dumps(
            results,
            indent=2,
        )
    )

    print()
    print(
        f"Wrote {out_path}"
    )


if __name__ == "__main__":
    main()