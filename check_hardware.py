"""
check_hardware.py -- confirms the VNA and both switch boards are plugged
in, detected, and actually respond correctly -- WITHOUT needing the
FastAPI server (main.py/uvicorn) running. This calls the exact same
underlying check as `curl -X POST /api/bridge/connect` (bridge_hardware
.test_wired_connection()), just directly, since that function has no
FastAPI dependency to begin with.

Usage:
    python check_hardware.py
"""
import bridge_hardware


def main():
    print("Testing hardware connection (VNA + TX/RX switches) ...\n")

    result = bridge_hardware.test_wired_connection()

    print(f"VNA port:  {result['vna_port'] or 'NOT FOUND'}")
    print(f"TX port:   {result['tx_port'] or 'NOT FOUND'}")
    print(f"RX port:   {result['rx_port'] or 'NOT FOUND'}")
    print(f"Connected: {result['connected']}")
    print(f"Detail:    {result['detail']}")

    print()
    if result["connected"]:
        print("Hardware is connected and the VNA responded correctly to a "
              "real test sweep. Ready to run capture_labeled_scan.py")
    else:
        print("NOT ready -- see 'detail' above for the specific reason.")


if __name__ == "__main__":
    main()