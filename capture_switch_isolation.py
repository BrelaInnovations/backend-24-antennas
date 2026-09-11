"""
capture_switch_isolation.py -- isolation test #2: test EACH switch board
individually, with no antennas and no dependency on the other board.

Continues the elimination from capture_direct_thru.py, which already
cleared the VNA and the .cal file (direct-thru peak was at t=0.000ns,
the physically-correct near-zero delay for a short straight cable --
NOT the 1.780ns/~0.0045 artifact seen in every full-system capture).

That leaves the TX switch board and/or the RX switch board as the
remaining suspects. This script tests them ONE AT A TIME, each wired
directly to both VNA ports so no jumper between the two boards and no
antenna is needed:

  TEST A -- TX board alone:
      VNA port 1 ---- TX board COMMON port
      VNA port 2 ---- TX board's CHANNEL 1 output   (direct jumper)
    (RX board and all antennas disconnected entirely)
    Script selects channel 1 on the TX board, then captures.

  TEST B -- RX board alone:
      VNA port 1 ---- RX board's CHANNEL 1 output   (direct jumper)
      VNA port 2 ---- RX board COMMON port
    (TX board and all antennas disconnected entirely)
    Script selects channel 1 on the RX board, then captures.

Interpreting the result (compare to direct-thru's clean t=0.000ns, and
to every full-system capture's t=1.780ns/mag~0.0045):
  - If TEST A shows the 1.780ns artifact -> it's the TX switch board.
  - If TEST B shows it -> it's the RX switch board.
  - If NEITHER shows it -> the artifact only appears when BOTH boards
    (or an antenna) are in the loop together -- a combined/interaction
    effect, not a single faulty board. Worth knowing either way.

Usage:
    python capture_switch_isolation.py
"""
import json
import os

import numpy as np

import hardware
import calibration as vna_calibration
from scan_engine import process_sweep_data
from capture_direct_thru import check_artifact_peak

CALIBRATION_FILE = "2-6_cal_with_new_cable.cal"
START_HZ = int(2000.0 * 1e6)
STOP_HZ = int(6000.0 * 1e6)
POINTS = 101
NUM_SWEEP_AVERAGES = 10
CHANNEL_TO_TEST = 1


def capture_averaged_sweep(vna_ser, cal):
    sweeps = []
    for i in range(NUM_SWEEP_AVERAGES):
        print(f"  sweep {i+1}/{NUM_SWEEP_AVERAGES} ...")
        hardware.set_vna_sweep(vna_ser, START_HZ, STOP_HZ, POINTS)
        from time import sleep
        sleep(0.1)
        hardware.clear_vna_fifo(vna_ser)
        raw = hardware.read_vna_data(vna_ser, POINTS)
        sweep_data = hardware.parse_vna_data(raw, POINTS)
        freqs, s21_db, s21_complex_list = process_sweep_data(
            sweep_data, START_HZ, STOP_HZ, POINTS, calibration=cal)
        sweeps.append({
            "freqs": freqs,
            "s21_real": [c.real for c in s21_complex_list],
            "s21_imag": [c.imag for c in s21_complex_list],
        })
    avg = {"freqs": sweeps[0]["freqs"]}
    real_stack = np.array([s["s21_real"] for s in sweeps])
    imag_stack = np.array([s["s21_imag"] for s in sweeps])
    avg["s21_real"] = real_stack.mean(axis=0).tolist()
    avg["s21_imag"] = imag_stack.mean(axis=0).tolist()
    return avg


def run_test(board_label, board_port, out_file):
    print(f"\n=== TEST: {board_label} board alone, channel {CHANNEL_TO_TEST} ===")
    input("Press Enter once wired and confirmed, or Ctrl+C to abort...")

    detected = hardware.auto_detect_devices()
    if not detected["vna_port"]:
        raise RuntimeError(f"Could not auto-detect VNA: {detected}")

    vna_ser, board_ser = None, None
    try:
        vna_ser, _b, _e = hardware.open_serial_connection_with_fallbacks(
            detected["vna_port"], "Auto", "VNA")
        if not vna_ser:
            raise RuntimeError("Failed to open VNA serial connection")

        board_ser, _b2, _e2 = hardware.open_serial_connection_with_fallbacks(
            board_port, "Auto", board_label)
        if not board_ser:
            raise RuntimeError(f"Failed to open {board_label} board serial connection")

        cmd = hardware.format_switch_command(CHANNEL_TO_TEST)
        hardware.send_switch_command(board_ser, cmd)
        print(f"Selected channel {CHANNEL_TO_TEST} on {board_label} board ({cmd.strip()})")

        cal = None
        import pathlib
        if pathlib.Path(CALIBRATION_FILE).exists():
            cal = vna_calibration.get_calibration(CALIBRATION_FILE)
        else:
            print(f"WARNING: {CALIBRATION_FILE} not found -- running uncorrected")

        print(f"Capturing ({NUM_SWEEP_AVERAGES} averaged sweeps)...")
        avg = capture_averaged_sweep(vna_ser, cal)
    finally:
        for ser in (vna_ser, board_ser):
            if ser:
                try:
                    ser.close()
                except Exception:
                    pass

    os.makedirs("dataset", exist_ok=True)
    with open(out_file, "w") as f:
        json.dump(avg, f)
    print(f"Saved {out_file}")
    check_artifact_peak(avg, label=f"{board_label}_isolation")


def find_board_port(role: str) -> str | None:
    """Look up the currently-connected port for 'tx' or 'rx' by matching
    its serial number against the saved switch_role_config.json -- works
    even with only ONE board connected (unlike resolve_tx_rx_ports, which
    needs both present to tell them apart). That's exactly the situation
    this isolation test needs, since the whole point is testing one
    board with the other physically disconnected."""
    detected = hardware.auto_detect_devices()
    cfg = hardware.load_switch_role_config()
    target_serial = cfg.get(f"{role}_serial")
    if not target_serial:
        return None
    for port, serial_number in detected["switch_ports"]:
        if serial_number == target_serial:
            return port
    return None


def main():
    print("=== Switch board isolation test ===")
    print("Continues from capture_direct_thru.py (VNA/cal already cleared).")
    print("This tests the TX and RX switch boards ONE AT A TIME.\n")

    print("--- TEST A: TX board alone ---")
    print("Wire:  VNA port 1 -> TX board COMMON port")
    print(f"       VNA port 2 -> TX board CHANNEL {CHANNEL_TO_TEST} output (direct jumper)")
    print("       (RX board and all antennas disconnected)")
    tx_port = find_board_port("tx")
    if not tx_port:
        raise RuntimeError(
            "Could not find the TX board's saved serial number among connected "
            "devices. Check it's plugged in and data/switch_role_config.json "
            "still has a 'tx_serial' entry.")
    run_test("TX", tx_port, "dataset/tx_isolation_test.json")

    print("\n--- TEST B: RX board alone ---")
    print("Wire:  VNA port 1 -> RX board CHANNEL {} output (direct jumper)".format(CHANNEL_TO_TEST))
    print("       VNA port 2 -> RX board COMMON port")
    print("       (TX board and all antennas disconnected)")
    rx_port = find_board_port("rx")
    if not rx_port:
        raise RuntimeError(
            "Could not find the RX board's saved serial number among connected "
            "devices. Check it's plugged in (and the TX board can stay "
            "connected or not -- doesn't matter for this lookup method) and "
            "data/switch_role_config.json still has an 'rx_serial' entry.")
    run_test("RX", rx_port, "dataset/rx_isolation_test.json")

    print("\n=== Both tests done. Compare both printed peaks to: ===")
    print("    direct_thru (VNA/cal only): t=0.000ns, mag=0.042  <- clean, expected")
    print("    every full-system capture : t=1.780ns, mag~0.0045 <- the artifact")


if __name__ == "__main__":
    main()