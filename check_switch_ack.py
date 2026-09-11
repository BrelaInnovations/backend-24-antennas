"""
check_switch_ack.py -- tests whether the TX/RX switch boards reliably
CONFIRM the antenna they were actually commanded to switch to, rather
than assuming the command always lands correctly.

send_switch_command() already reads back a response after every command
(hardware.py line ~206) but nothing currently checks whether that
response actually matches what was requested. If it doesn't match some
percentage of the time, that's a communication/protocol reliability
issue (dropped bytes, garbled command, race condition) -- a different,
more fixable problem than physical switch/relay hardware quality.

Usage:
    python check_switch_ack.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import hardware

N_REPEATS_PER_ANTENNA = 20


def main():
    detected = hardware.auto_detect_devices()
    tx_port, rx_port, _cfg = hardware.resolve_tx_rx_ports(detected["switch_ports"])
    if not tx_port or not rx_port:
        print("Could not detect TX/RX switch ports.")
        return

    for name, port in [("TX", tx_port), ("RX", rx_port)]:
        print(f"\n=== Testing {name} switch board ({port}) ===")
        ser, _b, err = hardware.open_serial_connection_with_fallbacks(port, "Auto", name)
        if not ser:
            print(f"  Failed to open: {err}")
            continue

        mismatches = 0
        empty_responses = 0
        total = 0

        try:
            for antenna in range(1, 13):
                cmd = hardware.format_switch_command(antenna)
                for _ in range(N_REPEATS_PER_ANTENNA):
                    total += 1
                    response = hardware.send_switch_command(ser, cmd)
                    if not response.strip():
                        empty_responses += 1
                        continue
                    # Check whether the response actually contains/confirms
                    # the antenna number we commanded. Adjust this check if
                    # your board's ack format is different -- run once and
                    # print raw responses first if unsure of the format.
                    expected_marker = f"{antenna:02d}"
                    if expected_marker not in response and cmd.strip(";") not in response:
                        mismatches += 1
                        print(f"  MISMATCH: commanded antenna {antenna} ({cmd!r}), "
                              f"got response {response!r}")
        finally:
            ser.close()

        print(f"\n  {name}: {total} commands sent")
        print(f"  Empty/no response: {empty_responses}/{total} "
              f"({100*empty_responses/total:.1f}%)")
        print(f"  Mismatched confirmation: {mismatches}/{total} "
              f"({100*mismatches/total:.1f}%)")

        if empty_responses + mismatches == 0:
            print(f"  -> {name} board confirms every command correctly. "
                  f"Communication layer looks reliable.")
        else:
            print(f"  -> {name} board is NOT reliably confirming commands. "
                  f"This could explain (part of) the phase instability -- "
                  f"a communication/protocol issue, not necessarily bad RF hardware.")


if __name__ == "__main__":
    main()