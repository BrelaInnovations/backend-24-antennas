"""
measure_component.py -- measure return loss (S11) and, if wired, insertion
loss (S21) for ONE component or sub-chain at a time, plus a time-domain
peak check on the S11 response (same method as check_artifact_peak.py) so
you can see WHERE in time each component's reflection sits.

This is for building up the loss budget piece by piece: VNA alone, VNA +
cable1, VNA + cable1 + adapter, VNA + cable1 + adapter + switch board,
etc. Run it once per stage, compare the printed numbers.

Usage:
    python measure_component.py <label> [--s21]

    <label>  name for this test, e.g. "vna_alone", "cable1_smaMM",
              "adapter_sma_f_to_ipex", "tx_board_ch1"
    --s21    also measure insertion loss -- only pass this if VNA port 2
              is actually connected through the same chain (i.e. you're
              measuring a 2-port component/chain, not just terminating
              port 1 alone for a pure return-loss test)

WIRING FOR A RETURN-LOSS-ONLY TEST (no --s21):
    VNA port 1 -> the component/chain under test -> its far end left
    terminated in whatever the test calls for:
      - "VNA alone": a good 50-ohm load directly on VNA port 1 (if you
        have one) -- if not, note that and we'll interpret accordingly.
      - "cable1 alone": VNA port1 -> cable1 -> 50-ohm load on cable1's
        far end.
      - "cable1 + adapter": VNA port1 -> cable1 -> adapter -> load on
        the adapter's far end.
      - etc, adding one piece at a time.
    VNA port 2 stays disconnected for these.

WIRING FOR AN INSERTION-LOSS TEST (--s21):
    VNA port 1 -> component/chain under test -> VNA port 2. E.g. to
    measure cable1's own insertion loss: port1 -> cable1 -> port2
    directly, nothing else in between.

Saves dataset/component_<label>.json (raw freqs/s21_real/s21_imag AND
s11_real/s11_imag) and prints a summary.
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("label")
    parser.add_argument("--s21", action="store_true",
                         help="also measure insertion loss (port2 connected through the chain)")
    parser.add_argument("--board", choices=["tx", "rx"], default=None,
                         help="if the switch board is part of this chain, which one to select a channel on")
    parser.add_argument("--channel", type=int, default=None,
                         help="channel (1-8) to select on --board before measuring")
    args = parser.parse_args()

    if (args.board is None) != (args.channel is None):
        parser.error("--board and --channel must be given together")

    print(f"Measuring: {args.label}")
    print("VNA port 1 -> component/chain under test (this stays connected to the")
    print("switch board's COMMON port for the whole sequence, if a board is involved).")
    if args.s21:
        print("VNA port 2 -> other end of the same chain (insertion loss test).")
    else:
        print("Far end of the chain -> either open (per this stage of the test) or terminated.")
    input("Press Enter once wired and ready...")

    board_ser = None
    detected = hardware.auto_detect_devices()
    if not detected["vna_port"]:
        raise RuntimeError(f"Could not auto-detect VNA: {detected}")

    if args.board is not None:
        tx_port, rx_port, _cfg = hardware.resolve_tx_rx_ports(detected["switch_ports"])
        board_port = tx_port if args.board == "tx" else rx_port
        if not board_port:
            raise RuntimeError(f"Could not auto-detect {args.board} switch board: {detected}")
        board_ser, _b2, _e2 = hardware.open_serial_connection_with_fallbacks(
            board_port, "Auto", args.board.upper())
        if not board_ser:
            raise RuntimeError(f"Failed to open {args.board} board serial connection")
        hardware.send_switch_command(board_ser, hardware.format_switch_command(args.channel))
        sleep(0.05)
        print(f"Selected {args.board.upper()} channel {args.channel}.")

    vna_ser, _b, _e = hardware.open_serial_connection_with_fallbacks(
        detected["vna_port"], "Auto", "VNA")
    if not vna_ser:
        raise RuntimeError("Failed to open VNA serial connection")

    try:
        hardware.set_vna_sweep(vna_ser, START_HZ, STOP_HZ, POINTS)
        sleep(0.1)
        hardware.clear_vna_fifo(vna_ser)
        raw = hardware.read_vna_data(vna_ser, POINTS)
        points_data = hardware.parse_vna_data(raw, POINTS)
    finally:
        vna_ser.close()
        if board_ser:
            hardware.send_switch_command(board_ser, "OFF;")
            board_ser.close()

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

    s11_db = 20 * np.log10(np.clip(np.abs(s11), 1e-12, None))
    print(f"\n--- Return loss (S11) for '{args.label}' ---")
    print(f"  mean: {s11_db.mean():.2f} dB   worst (least negative): {s11_db.max():.2f} dB   "
          f"best: {s11_db.min():.2f} dB")

    t, s11_t = timedomain.to_time_domain(freqs_hz, s11, oversample=8)
    mask = t <= 30e-9
    mag = np.abs(s11_t[mask])
    peak_idx = int(np.argmax(mag))
    peak_t_ns = float(t[mask][peak_idx] * 1e9)
    peak_mag = float(mag[peak_idx])
    print(f"  time-domain peak: t={peak_t_ns:.3f}ns, magnitude={peak_mag:.5f}")
    print(f"  (compare this peak time against the known 1.78ns artifact)")

    if args.s21:
        s21_db = 20 * np.log10(np.clip(np.abs(s21), 1e-12, None))
        print(f"\n--- Insertion loss (S21) for '{args.label}' ---")
        print(f"  mean: {s21_db.mean():.2f} dB   worst: {s21_db.min():.2f} dB   best: {s21_db.max():.2f} dB")

    out = {
        "freqs": freqs_ghz,
        "s11_real": s11.real.tolist(),
        "s11_imag": s11.imag.tolist(),
        "s21_real": s21.real.tolist(),
        "s21_imag": s21.imag.tolist(),
    }
    out_path = Path("dataset") / f"component_{args.label}.json"
    out_path.parent.mkdir(exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(out, f)
    print(f"\nSaved {out_path}")


if __name__ == "__main__":
    main()