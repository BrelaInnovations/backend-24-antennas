"""
capture_isolation_channel.py -- redo of the switch-board isolation test,
one specific channel at a time, with proper termination.

IMPORTANT -- do this BEFORE running:
    Whatever port you're NOT actively testing on the selected switch
    board (i.e. every other one of its 8 channels) should already be
    fine -- the switch only connects the ONE selected channel to the
    common line, the rest are internally disconnected. The thing that
    matters is what's connected to the SELECTED channel's antenna port:
    it must be either a real antenna or a proper 50-ohm terminator.
    Do NOT leave it open/unconnected -- an open connector creates its
    own strong reflection that has nothing to do with the switch board,
    and would make this test meaningless.

Usage:
    python capture_isolation_channel.py <board> <channel> <output_label>

    <board>   "tx" or "rx" -- which switch board to test
    <channel> 1-8 -- which channel to select on that board
    <output_label> name for the output file, e.g. "tx_ch1_terminated"

Wiring for this test (same as your original isolation test):
    VNA port 1 (fwd)  -> DPDT bypassed -> switch board's COMMON input
    VNA port 2 (thru) -> the switch board's SELECTED channel output
                         (with antenna or 50-ohm terminator attached)

Saves dataset/<output_label>.json in the same {"freqs", "s21_real",
"s21_imag"} format as your original tx_isolation_test.json /
rx_isolation_test.json, so it's directly comparable -- run
check_artifact_peak.py-style analysis on it the same way.

Run this for at least 2 different channels on EACH board (e.g. tx
channel 1 and channel 4, rx channel 1 and channel 4) -- 4 captures
total -- so we can confirm the artifact really is channel-independent
under proper termination, not an artifact of one specific setup.
"""
import sys
import os
import json
from pathlib import Path
from time import sleep

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import hardware
import scan_engine
import calibration as vna_calibration

START_HZ = int(2.0e9)
STOP_HZ = int(6.0e9)
POINTS = 101
CALIBRATION_FILE = Path("2-6_cal_with_new_cable.cal")


def main():
    if len(sys.argv) != 4:
        print(f"Usage: python {sys.argv[0]} <tx|rx> <channel 1-8> <output_label>")
        sys.exit(1)

    board = sys.argv[1].lower()
    channel = int(sys.argv[2])
    label = sys.argv[3]

    if board not in ("tx", "rx"):
        print("First argument must be 'tx' or 'rx'")
        sys.exit(1)
    if not (1 <= channel <= 8):
        print("Channel must be 1-8")
        sys.exit(1)

    print(f"Testing {board.upper()} board, channel {channel}.")
    print("Make sure: VNA port1 -> board common input, VNA port2 -> the")
    print(f"selected channel {channel}'s antenna port, which must have a")
    print("real antenna OR a 50-ohm terminator on it (not left open).")
    input("Press Enter once wired and ready...")

    detected = hardware.auto_detect_devices()
    tx_port, rx_port, _cfg = hardware.resolve_tx_rx_ports(detected["switch_ports"])
    board_port = tx_port if board == "tx" else rx_port
    if not detected["vna_port"] or not board_port:
        raise RuntimeError(f"Could not auto-detect required devices: {detected}")

    vna_ser, _b1, _e1 = hardware.open_serial_connection_with_fallbacks(
        detected["vna_port"], "Auto", "VNA")
    board_ser, _b2, _e2 = hardware.open_serial_connection_with_fallbacks(
        board_port, "Auto", board.upper())
    if not (vna_ser and board_ser):
        raise RuntimeError("Failed to open VNA or switch board serial connection")

    cal = None
    if CALIBRATION_FILE.exists():
        cal = vna_calibration.get_calibration(str(CALIBRATION_FILE))
    else:
        print(f"WARNING: {CALIBRATION_FILE} not found -- running uncorrected")

    try:
        hardware.send_switch_command(board_ser, hardware.format_switch_command(channel))
        sleep(0.05)

        hardware.set_vna_sweep(vna_ser, START_HZ, STOP_HZ, POINTS)
        sleep(0.1)
        hardware.clear_vna_fifo(vna_ser)
        raw = hardware.read_vna_data(vna_ser, POINTS)
        sweep_data = hardware.parse_vna_data(raw, POINTS)

        freqs, s21_db, s21_complex_list = scan_engine.process_sweep_data(
            sweep_data, START_HZ, STOP_HZ, POINTS, calibration=cal)

        hardware.send_switch_command(board_ser, "OFF;")

        out = {
            "freqs": freqs,
            "s21_real": [c.real for c in s21_complex_list],
            "s21_imag": [c.imag for c in s21_complex_list],
        }
        out_path = Path("dataset") / f"{label}.json"
        out_path.parent.mkdir(exist_ok=True)
        with open(out_path, "w") as f:
            json.dump(out, f)
        print(f"Saved {out_path}")
    finally:
        for ser in (vna_ser, board_ser):
            try:
                if ser:
                    ser.close()
            except Exception:
                pass


if __name__ == "__main__":
    main()