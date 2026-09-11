"""
check_freq_idx_integrity.py -- tests whether the VNA's freq_idx field is
ALWAYS sequential (0, 1, 2, ..., 100) and never dropped/duplicated/out of
order. Your parser currently assumes arrival order == frequency order and
never checks this. If it's ever wrong, every frequency bin after that
point gets silently misaligned -- which would look exactly like random,
pair-dependent "phase instability" with no relationship to real hardware
quality, since it's actually comparing the wrong frequencies against each
other.

This requires a small, SAFE change: read parse_vna_data()'s freq_idx
field (already captured, just unused) and check it directly, without
touching any other acquisition code.

Usage:
    python check_freq_idx_integrity.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import hardware
import calibration as vna_calibration
from pathlib import Path
from struct import unpack_from

START_HZ = int(2000.0 * 1e6)
STOP_HZ = int(6000.0 * 1e6)
POINTS = 101
NUM_TEST_SWEEPS = 10  # across several pairs, several sweeps each

TEST_PAIRS = [(6, 3), (6, 6), (2, 3), (5, 3), (6, 2)]  # (tx, rx) -- mix of "bad" and "good" pairs from your logs


def raw_freq_indices(raw_bytes, points):
    """Directly extract freq_idx from each 32-byte block, bypassing the
    normal parser entirely -- we want the raw truth, not a reprocessed
    version."""
    indices = []
    for i in range(points):
        block = raw_bytes[i * 32:(i + 1) * 32]
        if len(block) < 32:
            indices.append(None)  # short block -- itself a problem, flag it
            continue
        *_ignored, freq_idx = unpack_from("<iiiiiihxxxxxx", block)
        indices.append(freq_idx)
    return indices


def main():
    detected = hardware.auto_detect_devices()
    tx_port, rx_port, _cfg = hardware.resolve_tx_rx_ports(detected["switch_ports"])
    if not detected["vna_port"] or not tx_port or not rx_port:
        print("Could not detect hardware.")
        return

    vna_ser, _b1, _e1 = hardware.open_serial_connection_with_fallbacks(detected["vna_port"], "Auto", "VNA")
    tx_ser, _b2, _e2 = hardware.open_serial_connection_with_fallbacks(tx_port, "Auto", "TX")
    rx_ser, _b3, _e3 = hardware.open_serial_connection_with_fallbacks(rx_port, "Auto", "RX")
    if not (vna_ser and tx_ser and rx_ser):
        print("Failed to open serial connections.")
        return

    print(f"Testing freq_idx integrity across {NUM_TEST_SWEEPS} sweeps for "
          f"{len(TEST_PAIRS)} pairs. Device should stay EMPTY, untouched.\n")

    total_problems = 0
    total_checks = 0

    try:
        for tx, rx in TEST_PAIRS:
            for sweep_i in range(NUM_TEST_SWEEPS):
                hardware.send_switch_command(tx_ser, hardware.format_switch_command(tx))
                hardware.send_switch_command(rx_ser, hardware.format_switch_command(rx))
                import time
                time.sleep(0.01)

                hardware.set_vna_sweep(vna_ser, START_HZ, STOP_HZ, POINTS)
                time.sleep(0.1)
                hardware.clear_vna_fifo(vna_ser)
                raw = hardware.read_vna_data(vna_ser, POINTS)

                indices = raw_freq_indices(raw, POINTS)
                total_checks += 1

                expected = list(range(POINTS))
                # Some firmwares' freq_idx might not start at 0 or might use
                # a different base -- so check RELATIVE ordering (strictly
                # increasing by 1 each step) rather than assuming it must
                # literally equal range(101). That's the real invariant we
                # care about for "does arrival order == frequency order".
                none_count = sum(1 for x in indices if x is None)
                diffs = [indices[i+1] - indices[i] for i in range(len(indices)-1)
                         if indices[i] is not None and indices[i+1] is not None]
                non_unit_steps = [d for d in diffs if d != 1]

                if none_count > 0 or non_unit_steps:
                    total_problems += 1
                    print(f"[PROBLEM] TX{tx}-RX{rx} sweep {sweep_i+1}: "
                          f"{none_count} short/missing blocks, "
                          f"{len(non_unit_steps)} non-sequential steps "
                          f"(expected all steps == 1, got e.g. {non_unit_steps[:5]})")
                    print(f"          first 10 freq_idx values: {indices[:10]}")
                else:
                    print(f"[OK]      TX{tx}-RX{rx} sweep {sweep_i+1}: "
                          f"freq_idx perfectly sequential ({indices[0]}..{indices[-1]})")

        hardware.send_switch_command(tx_ser, "OFF;")
        hardware.send_switch_command(rx_ser, "OFF;")
    finally:
        for ser in (vna_ser, tx_ser, rx_ser):
            try:
                if ser:
                    ser.close()
            except Exception:
                pass

    print()
    print(f"Total sweeps checked: {total_checks}")
    print(f"Sweeps with freq_idx problems: {total_problems}")
    print()
    if total_problems == 0:
        print("freq_idx is always perfectly sequential -- this hypothesis is "
              "RULED OUT. The instability is not coming from frequency "
              "misalignment; arrival order can be trusted.")
    else:
        print(f"freq_idx integrity FAILED on {total_problems}/{total_checks} sweeps "
              "-- this is very likely a real contributor to the instability. "
              "Every frequency bin after a misordered/dropped block would be "
              "silently compared against the wrong frequency in later analysis.")


if __name__ == "__main__":
    main()