"""
map_channel_stability.py

Tests the stability pattern around the previously bad TX6-RX3 path.

Runs 3 consecutive full sweeps and calculates the mean phase difference
between consecutive sweeps for selected TX/RX pairs.

Purpose:
    Determine whether instability follows TX6, RX3, or only the
    TX6 <-> RX3 combination.

IMPORTANT:
    Device must remain EMPTY.
    Do NOT touch, move, disconnect, or reconnect anything.
"""

import sys
import os
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
NUM_SWEEPS = 10

CALIBRATION_FILE = Path("2-6_cal_with_new_cable.cal")


# All pairs involving TX6
TX6_PAIRS = [
    "TX6-RX1",
    "TX6-RX2",
    "TX6-RX3",
    "TX6-RX4",
    "TX6-RX5",
    "TX6-RX6",
    "TX6-RX7",
    "TX6-RX8",
]

# All pairs involving RX3
RX3_PAIRS = [
    "TX1-RX3",
    "TX2-RX3",
    "TX3-RX3",
    "TX4-RX3",
    "TX5-RX3",
    "TX6-RX3",
    "TX7-RX3",
    "TX8-RX3",
]

PAIRS = list(dict.fromkeys(TX6_PAIRS + RX3_PAIRS))


def capture_sweeps():

    detected = hardware.auto_detect_devices()

    tx_port, rx_port, _cfg = (
        hardware.resolve_tx_rx_ports(
            detected["switch_ports"]
        )
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

        results = []

        for i in range(NUM_SWEEPS):

            print(
                f"\n========== SWEEP {i + 1}/{NUM_SWEEPS} =========="
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

            results.append(sweep)

        return results

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


def get_spectrum(data):

    re = data.get("s21_real")
    im = data.get("s21_imag")

    if (
        not re
        or not im
        or len(re) != len(im)
    ):
        return None

    return (
        np.asarray(re)
        + 1j * np.asarray(im)
    )


def phase_difference(a, b):

    diff = np.angle(
        np.exp(
            1j * (
                np.angle(b)
                - np.angle(a)
            )
        )
    )

    return np.degrees(
        np.abs(diff)
    )


def analyze_pair(sweeps, pair):

    spectra = []

    for sweep in sweeps:

        data = sweep.get(pair)

        if not data:
            continue

        spectrum = get_spectrum(data)

        if spectrum is not None:
            spectra.append(spectrum)

    if len(spectra) < 2:
        return None

    differences = []

    for i in range(len(spectra) - 1):

        diff = phase_difference(
            spectra[i],
            spectra[i + 1],
        )

        differences.append(diff)

    differences = np.asarray(differences)

    mean_per_frequency = np.mean(
        differences,
        axis=0
    )

    max_per_frequency = np.max(
        differences,
        axis=0
    )

    all_magnitudes = np.mean(
        np.asarray([
            np.abs(s)
            for s in spectra
        ]),
        axis=0,
    )

    return {
        "mean_phase_deg":
            float(np.mean(mean_per_frequency)),

        "max_phase_deg":
            float(np.max(max_per_frequency)),

        "mean_magnitude":
            float(np.mean(all_magnitudes)),
    }


def print_matrix(results):

    print()
    print("=" * 90)
    print("PHASE-STABILITY MATRIX")
    print("Values = mean phase difference between consecutive sweeps")
    print("=" * 90)

    print()
    print(
        f"{'':8s}"
        + "".join(
            f"{('RX' + str(rx)):>10s}"
            for rx in range(1, 9)
        )
    )

    print("-" * 88)

    for tx in range(1, 9):

        row = f"TX{tx:<5}"

        for rx in range(1, 9):

            pair = f"TX{tx}-RX{rx}"

            if pair in results:

                value = results[pair]["mean_phase_deg"]

                row += f"{value:10.1f}"

            else:

                row += f"{'---':>10s}"

        print(row)

    print()
    print("Legend:")
    print("  < 10°     = very stable")
    print("  10–20°    = mildly variable")
    print("  20–40°    = unstable")
    print("  > 40°     = strongly unstable")
    print()


def main():

    print()
    print("CHANNEL STABILITY DIAGNOSTIC")
    print()
    print("EMPTY DEVICE ONLY.")
    print("Do NOT touch or reconnect anything.")
    print()
    print("Testing:")
    print("  • every TX6 → RX pair")
    print("  • every TX → RX3 pair")
    print()
    print("This requires 3 complete 64-pair sweeps.")
    print()

    sweeps = capture_sweeps()

    results = {}

    for pair in PAIRS:

        result = analyze_pair(
            sweeps,
            pair,
        )

        if result is not None:
            results[pair] = result

    print_matrix(results)

    print("=" * 90)
    print("DETAILED RESULTS")
    print("=" * 90)

    for pair in PAIRS:

        if pair not in results:
            continue

        r = results[pair]

        print(
            f"{pair:12s}"
            f" mean={r['mean_phase_deg']:7.2f}°"
            f" max={r['max_phase_deg']:7.2f}°"
            f" mag={r['mean_magnitude']:.5e}"
        )

    out = Path(
        "data/channel_stability_results.json"
    )

    out.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    import json

    out.write_text(
        json.dumps(
            results,
            indent=2,
        )
    )

    print()
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()