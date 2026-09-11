"""
bridge_hardware.py — connects the /bridge/* API endpoints to real hardware.

Deliberately has NO dependency on FastAPI, MongoDB, or server.py, so it can
be unit-tested standalone. server.py's bridge_scan/bridge_connect/
bridge_status endpoints call into this module.

HARDWARE_SIMULATE controls the fallback:
  - true  (default right now): real hardware calls are skipped entirely;
           used only for the "simulated" transport option, which already
           existed in server.py and must keep working unchanged.
  - false: "wired" transport actually talks to hardware.py.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

import hardware

logger = logging.getLogger("naibra.bridge_hardware")

HARDWARE_SIMULATE = os.environ.get("HARDWARE_SIMULATE", "true").lower() != "false"


def discover_devices() -> list[dict]:
    """
    Real device discovery for the 'wired' transport (used by /bridge/scan
    when not in simulate mode). Returns devices in the same shape the
    mobile app already expects: {id, name, rssi, type}.
    """
    detected = hardware.auto_detect_devices()
    devices: list[dict] = []

    if detected["vna_port"]:
        devices.append(
            {"id": detected["vna_port"], "name": "NanoVNA", "rssi": None, "type": "wired"}
        )

    tx_port, rx_port, _cfg = hardware.resolve_tx_rx_ports(detected["switch_ports"])
    if tx_port:
        devices.append({"id": tx_port, "name": "TX Switch Board", "rssi": None, "type": "wired"})
    if rx_port:
        devices.append({"id": rx_port, "name": "RX Switch Board", "rssi": None, "type": "wired"})

    return devices


def test_wired_connection() -> dict:
    """
    Real connection test for the 'wired' transport (used by /bridge/connect
    and /bridge/status when not in simulate mode). Opens the VNA, runs a
    tiny 2-point sweep to confirm it actually responds, then closes it.

    Returns:
        {
          "connected": bool,
          "vna_port": str | None,
          "tx_port": str | None,
          "rx_port": str | None,
          "detail": str,
        }
    """
    detected = hardware.auto_detect_devices()

    if not detected["vna_port"]:
        return {
            "connected": False,
            "vna_port": None,
            "tx_port": None,
            "rx_port": None,
            "detail": "No VNA detected on any serial port.",
        }

    tx_port, rx_port, _cfg = hardware.resolve_tx_rx_ports(detected["switch_ports"])
    if not tx_port or not rx_port:
        return {
            "connected": False,
            "vna_port": detected["vna_port"],
            "tx_port": tx_port,
            "rx_port": rx_port,
            "detail": f"Could not resolve TX/RX switch boards "
                      f"(found {len(detected['switch_ports'])}, need 2).",
        }

    vna_ser, _baud, errors = hardware.open_serial_connection_with_fallbacks(
        detected["vna_port"], "Auto", label_for_logs="VNA"
    )
    if not vna_ser:
        return {
            "connected": False,
            "vna_port": detected["vna_port"],
            "tx_port": tx_port,
            "rx_port": rx_port,
            "detail": f"Failed to open VNA port: {errors}",
        }

    try:
        hardware.set_vna_sweep(vna_ser, 1_000_000_000, 1_100_000_000, 2)
        hardware.clear_vna_fifo(vna_ser)
        raw = hardware.read_vna_data(vna_ser, 2)
        ok = len(raw) >= 64
    except Exception as e:
        logger.exception("VNA test read failed")
        return {
            "connected": False,
            "vna_port": detected["vna_port"],
            "tx_port": tx_port,
            "rx_port": rx_port,
            "detail": f"VNA opened but test read failed: {e}",
        }
    finally:
        vna_ser.close()

    return {
        "connected": ok,
        "vna_port": detected["vna_port"],
        "tx_port": tx_port,
        "rx_port": rx_port,
        "detail": "VNA responded correctly." if ok else "VNA did not respond as expected.",
    }