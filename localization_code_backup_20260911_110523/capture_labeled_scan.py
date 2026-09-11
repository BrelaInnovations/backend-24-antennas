"""
capture_labeled_scan.py -- capture one real scan and record it as a
labeled example (known true target position) for validate.py.

Usage:
    python capture_labeled_scan.py <label> <true_x_cm> <true_y_cm> <true_z_cm>

Example (target measured at x=2.0, y=-1.5, z=4.0 relative to dome base
center, apex pointing up along +z -- same origin as
core.geometry.physical_antenna_positions(), apex at (0,0,8)):
    python capture_labeled_scan.py "metal ball pos A" 2.0 -1.5 4.0

Each run:
  1. Auto-detects the VNA + TX/RX switch serial ports (same as main.py)
  2. Runs 3 averaged sweeps across all 144 pairs (same as main.py)
  3. Saves the raw sweep to dataset/<label>.json
  4. Appends {"label", "file", "true_position_cm"} to dataset/manifest.json
  5. Prints DAS + dot-score results automatically

Place the target, MEASURE ITS POSITION FIRST (ruler/calipers, relative
to dome base center), then run one capture per position. Aim for at
least 8-10 different positions spread around the dome -- including some
off-center and at different depths -- for a meaningful validate.py
report. Keep the dome otherwise undisturbed between captures (same
cables, same connections) so the calibration stays valid.
"""
import sys
import os
import json
import pathlib
from time import sleep


import hardware
import scan_engine
import calibration as vna_calibration  # the VNA .cal file loader, NOT core/calibration.py
import dot_scoring

DATASET_DIR = "dataset"
MANIFEST_FILE = os.path.join(DATASET_DIR, "manifest.json")
CALIBRATION_FILE = pathlib.Path("2-6_cal_with_new_cable.cal")
BASELINE_FILE = os.path.join("data", "baseline_full_sweep.json")

NUM_ANTENNAS = 12
START_HZ = int(2000.0 * 1e6)
STOP_HZ = int(6000.0 * 1e6)
POINTS = 101
NUM_SWEEP_AVERAGES = 3 


def print_scan_scores(sweep_plot_data):
    """Auto-run after every capture: DAS confidence + dot-cloud weights,
    against the saved baseline if one exists. Works the same whether the
    dome is empty or has a target in it -- an empty dome should come back
    low-confidence/no-result, a real target should come back confident."""
    import das_imaging

    print("\n--- Scores ---")

    _, raw_values = scan_engine.compute_sensor_weights_from_traces(sweep_plot_data)

    baseline_raw_path = "data/baseline_raw_s21.json"
    if not os.path.exists(baseline_raw_path):
        print(f"\nNo raw baseline found at {baseline_raw_path} -- run capture_baseline.py "
              f"first (it now saves this automatically) to get an accurate severity score.")
        return

    with open(baseline_raw_path) as f:
        baseline_raw = json.load(f)

    baseline_relative_weights = dot_scoring.compute_weights_from_baseline(raw_values, baseline_raw)
    top_pairs = sorted(baseline_relative_weights, key=lambda l: -baseline_relative_weights[l])[:5]
    print("Top 5 dot-score pairs (deviation from empty-device baseline):")
    for label in top_pairs:
        print(f"  {label}: weight={baseline_relative_weights[label]:.3f}  avg_s21_db={raw_values[label]:.2f}")

    side_result = dot_scoring.simulate_side_from_real_data(baseline_relative_weights)
    print(f"\nSeverity score: {side_result['score']}/100")
    print(f"Max severity: {side_result['max_severity']}  Mean severity: {side_result['mean_severity']}")
    print(f"Dot counts: {side_result['dot_counts']}")
    print(f"Worst region: {side_result['worst_region']}")
    if not os.path.exists(BASELINE_FILE):
        print(f"\nNo baseline found at {BASELINE_FILE} -- run capture_baseline.py "
              f"first to also get a DAS result here.")
        return

    with open(BASELINE_FILE) as f:
        baseline = json.load(f)

    from core import calibration as core_cal
    usable = list(core_cal.iter_usable_pairs(sweep_plot_data))
    print(f"Usable pairs feeding DAS: {len(usable)} / 64")

    results = das_imaging.run_das(sweep_plot_data, baseline_plot_data=baseline)
    if results:
        top = results[0]
        confidence = das_imaging.snr_check(results)
        print(f"\nDAS candidate (not a confirmed detection): x={top['x']:.2f} y={top['y']:.2f} z={top['z']:.2f} "
            f"intensity={top['intensity']!r} coherence={top['coherence']:.4f}")
        print(f"DAS confidence: {confidence}")
        if not confidence['confident']:
            print("No confident location: do not treat this candidate as a detected target.")
    else:
        print("\nDAS: NO RESULT")
    print("--- End scores ---\n")


def capture_one_sweep():
    detected = hardware.auto_detect_devices()
    tx_port, rx_port, _cfg = hardware.resolve_tx_rx_ports(detected["switch_ports"])
    if not detected["vna_port"] or not tx_port or not rx_port:
        raise RuntimeError(f"Could not auto-detect all devices: {detected}")

    vna_ser, tx_ser, rx_ser = None, None, None
    try:
        vna_ser, _b1, _e1 = hardware.open_serial_connection_with_fallbacks(detected["vna_port"], "Auto", "VNA")
        tx_ser, _b2, _e2 = hardware.open_serial_connection_with_fallbacks(tx_port, "Auto", "TX")
        rx_ser, _b3, _e3 = hardware.open_serial_connection_with_fallbacks(rx_port, "Auto", "RX")
        if not (vna_ser and tx_ser and rx_ser):
            raise RuntimeError("Failed to open one or more serial connections")

        cal = None
        if CALIBRATION_FILE.exists():
            cal = vna_calibration.get_calibration(str(CALIBRATION_FILE))
        else:
            print(f"WARNING: {CALIBRATION_FILE} not found -- running uncorrected")

        def _run_averaged_sweep_set():
            raw_sweeps = []
            for i in range(NUM_SWEEP_AVERAGES):
                print(f"  sweep {i+1}/{NUM_SWEEP_AVERAGES} ...")
                raw_sweeps.append(scan_engine.run_full_sweep(
                    vna_ser, tx_ser, rx_ser, START_HZ, STOP_HZ,
                    num_antennas=NUM_ANTENNAS, points=POINTS, calibration=cal,
                ))
            return scan_engine.average_sweeps(raw_sweeps)

        return _run_averaged_sweep_set()
    finally:
        for ser in (vna_ser, tx_ser, rx_ser):
            try:
                if ser:
                    ser.close()
            except Exception:
                pass


def main():
    if len(sys.argv) != 5:
        print(__doc__)
        sys.exit(1)

    label = sys.argv[1]
    true_x, true_y, true_z = (float(sys.argv[2]), float(sys.argv[3]), float(sys.argv[4]))

    os.makedirs(DATASET_DIR, exist_ok=True)

    print(f"Capturing scan for label={label!r} at true position "
          f"({true_x}, {true_y}, {true_z}) cm ...")

    sweep_plot_data = capture_one_sweep()

    safe_label = label.replace(" ", "_").replace("/", "_")
    scan_file = os.path.join(DATASET_DIR, f"{safe_label}.json")
    with open(scan_file, "w") as f:
        json.dump(sweep_plot_data, f)

    manifest = []
    if os.path.exists(MANIFEST_FILE):
        with open(MANIFEST_FILE) as f:
            manifest = json.load(f)

    manifest = [m for m in manifest if m["label"] != label]  # replace if re-captured
    manifest.append({
        "label": label,
        "file": scan_file,
        "true_position_cm": [true_x, true_y, true_z],
    })

    with open(MANIFEST_FILE, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"Saved scan to {scan_file}")
    print(f"Manifest now has {len(manifest)} labeled scan(s).")
    print(f"Capture more at different positions, then run: python validate.py")

    print_scan_scores(sweep_plot_data)


if __name__ == "__main__":
    main()
