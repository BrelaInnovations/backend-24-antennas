"""
hardware.py — NaiBra hardware layer (NanoVNA + RF switch matrix)

Ported from the legacy Tkinter GUI's serial-protocol functions.
This module has ZERO GUI/Tkinter dependency and ZERO FastAPI dependency —
it's pure hardware I/O logic, so it can be tested standalone, unit-tested,
and later imported directly into the FastAPI backend without changes.

Protocols:
  - NanoVNA: binary register read/write over serial (write sweep config,
    clear FIFO, read raw IQ blocks, parse into complex S-parameters).
  - RF switch boards (TX/RX): simple ASCII command protocol ("P05;", "OFF;").
  - Device identification: VID:PID based auto-detection, since the VNA and
    the two switch boards are distinguishable by their USB chip identity
    (and the two switch boards are further told apart by serial number).
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from struct import pack, unpack_from
from time import sleep
from typing import Optional

import serial
import serial.tools.list_ports

logger = logging.getLogger("naibra.hardware")

# ------------------ Constants ------------------
BAUD = 115200
WRITE_SLEEP = 0.05
SERIAL_TIMEOUT = 2
NUM_ANTENNAS = 12

_CMD_WRITE8 = 0x23
_CMD_WRITE2 = 0x21
_CMD_WRITE = 0x20
_CMD_READFIFO = 0x18
_ADDR_SWEEP_START = 0x00
_ADDR_SWEEP_STEP = 0x10
_ADDR_SWEEP_POINTS = 0x20
_ADDR_SWEEP_VALS_PER_FREQ = 0x22
_ADDR_VALUES_FIFO = 0x30

DATA_DIR = "data"
SWITCH_ROLE_CONFIG_FILE = os.path.join(DATA_DIR, "switch_role_config.json")

BAUD_OPTIONS = ["Auto", "115200", "230400", "460800", "921600"]

# Identified from the hardware (see legacy GUI comments):
#   VNA        -> unique USB chip, VID:PID = 04B4:0008 (no serial number reported)
#   TX/RX subs -> shared USB chip, VID:PID = 2886:802F, distinguished by
#                 each board's own burned-in serial number.
VNA_VID_PID = (0x04B4, 0x0008)
VNA_ALT_VID_PID = (0x04B4, 0x0008)
SWITCH_VID_PID = (0x2886, 0x802F)


# ------------------ Device discovery ------------------
def list_ports_with_info():
    """Return raw ListPortInfo objects (device, vid, pid, serial_number, ...)."""
    return list(serial.tools.list_ports.comports())


def load_switch_role_config() -> dict:
    if os.path.exists(SWITCH_ROLE_CONFIG_FILE):
        try:
            with open(SWITCH_ROLE_CONFIG_FILE, "r") as f:
                return json.load(f)
        except Exception:
            logger.warning("Could not parse %s, ignoring.", SWITCH_ROLE_CONFIG_FILE)
            return {}
    return {}


def save_switch_role_config(cfg: dict) -> None:
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(SWITCH_ROLE_CONFIG_FILE, "w") as f:
            json.dump(cfg, f, indent=2)
    except Exception:
        logger.exception("Failed to save switch role config.")


def auto_detect_devices() -> dict:
    """
    Scan connected serial devices and identify:
      - the VNA port (matched by its unique VID:PID)
      - the two switch-board ports (matched by shared VID:PID), each tagged
        with its own serial number.

    Returns:
        {"vna_port": "COM11" or None, "switch_ports": [(port, serial_number), ...]}
    """
    result: dict = {"vna_port": None, "switch_ports": []}
    for p in list_ports_with_info():
        if p.vid is None or p.pid is None:
            continue
        vidpid = (p.vid, p.pid)
        if vidpid == VNA_VID_PID:
            result["vna_port"] = p.device
        elif vidpid == SWITCH_VID_PID:
            result["switch_ports"].append((p.device, p.serial_number or ""))
    return result


def resolve_tx_rx_ports(switch_ports: list) -> tuple[Optional[str], Optional[str], dict]:
    """
    Decide which detected switch board is TX and which is RX, using the
    remembered preference in SWITCH_ROLE_CONFIG_FILE. First time seeing a
    pair, assign deterministically (sorted serial order) and remember it.

    Returns (tx_port_or_None, rx_port_or_None, cfg_used)
    """
    if not switch_ports:
        return None, None, {}

    if len(switch_ports) == 1:
        # Can't tell TX/RX apart with only one board -- leave both
        # unassigned so callers can clearly see something's missing.
        return None, None, {}

    cfg = load_switch_role_config()
    serials_present = sorted(sn for _, sn in switch_ports if sn)

    tx_serial = cfg.get("tx_serial")
    rx_serial = cfg.get("rx_serial")
    known_pair = {tx_serial, rx_serial} == set(serials_present) and tx_serial and rx_serial

    if not known_pair:
        if len(serials_present) == 2:
            tx_serial, rx_serial = serials_present[0], serials_present[1]
        else:
            ports_sorted = sorted(switch_ports, key=lambda x: x[0])
            tx_serial, rx_serial = ports_sorted[0][1], ports_sorted[1][1]
        cfg = {"tx_serial": tx_serial, "rx_serial": rx_serial}
        save_switch_role_config(cfg)

    port_by_serial = {sn: dev for dev, sn in switch_ports}
    return port_by_serial.get(tx_serial), port_by_serial.get(rx_serial), cfg


def swap_switch_roles() -> dict:
    """Flip the remembered TX/RX serial assignment."""
    cfg = load_switch_role_config()
    if "tx_serial" in cfg and "rx_serial" in cfg:
        cfg["tx_serial"], cfg["rx_serial"] = cfg["rx_serial"], cfg["tx_serial"]
        save_switch_role_config(cfg)
    return cfg


# ------------------ Serial connection ------------------
def try_open_serial(port: str, baudrate: int, timeout: float = SERIAL_TIMEOUT):
    return serial.Serial(port, baudrate=baudrate, timeout=timeout)


def open_serial_connection_with_fallbacks(
    port: str, baud_selection: str, label_for_logs: str = ""
):
    """
    Try to open a serial port with the selected baud rate, or fall through
    a list of common rates if "Auto" is requested.

    Returns (serial_obj or None, used_baud or None, error_messages_list)
    """
    errors: list[str] = []
    if baud_selection == "Auto":
        rates = [115200, 230400, 460800, 921600]
    else:
        try:
            rates = [int(baud_selection)]
        except Exception:
            rates = [BAUD]

    for br in rates:
        try:
            ser = try_open_serial(port, br)
            logger.info("Opened %s port %s at %d bps", label_for_logs, port, br)
            return ser, br, errors
        except Exception as e:
            msg = f"[{label_for_logs}] Failed opening {port} at {br} bps: {e}"
            errors.append(msg)
            logger.warning(msg)
    return None, None, errors


# ------------------ RF switch protocol ------------------
def format_switch_command(port_number) -> str:
    try:
        p = int(port_number)
    except Exception:
        return "OFF;"
    return f"P{p:02d};" if 1 <= p <= NUM_ANTENNAS else "OFF;"


def send_switch_command(serial_port, cmd: str) -> str:
    if not serial_port:
        return ""
    try:
        if serial_port.is_open:
            serial_port.write(cmd.encode())
            sleep(0.05)
            return serial_port.read_all().decode(errors="ignore")
    except Exception:
        logger.exception("Failed sending switch command %r", cmd)
        return ""
    return ""


# ------------------ NanoVNA protocol ------------------
def set_vna_sweep(ser, start: int, stop: int, points: int) -> None:
    step = int((stop - start) / (points - 1))
    ser.write(pack("<BBQ", _CMD_WRITE8, _ADDR_SWEEP_START, int(start)))
    sleep(WRITE_SLEEP)
    ser.write(pack("<BBQ", _CMD_WRITE8, _ADDR_SWEEP_STEP, int(step)))
    sleep(WRITE_SLEEP)
    ser.write(pack("<BBH", _CMD_WRITE2, _ADDR_SWEEP_POINTS, points))
    sleep(WRITE_SLEEP)
    ser.write(pack("<BBH", _CMD_WRITE2, _ADDR_SWEEP_VALS_PER_FREQ, 1))
    sleep(WRITE_SLEEP)


def clear_vna_fifo(ser) -> None:
    ser.write(pack("<BBB", _CMD_WRITE, _ADDR_VALUES_FIFO, 0))
    sleep(WRITE_SLEEP)


def read_vna_data(ser, points: int) -> bytes:
    data = b""
    points_remaining = points
    while points_remaining > 0:
        points_to_read = min(255, points_remaining)
        ser.write(pack("<BBB", _CMD_READFIFO, _ADDR_VALUES_FIFO, points_to_read))
        sleep(WRITE_SLEEP)
        n_bytes = points_to_read * 32
        chunk = ser.read(n_bytes)
        if len(chunk) < n_bytes:
            raise serial.SerialTimeoutException(
                f"VNA read timeout: expected {n_bytes} bytes, got {len(chunk)}"
            )
        data += chunk
        points_remaining -= points_to_read
    return data


def parse_vna_data(data: bytes, points: int) -> list[dict]:
    """
    CRITICAL FIX: the VNA's freq_idx does NOT reliably start at 0 for
    each read -- confirmed empirically (check_freq_idx_integrity.py)
    that reads consistently wrap partway through a rotating internal
    buffer, with the rotation point CHANGING between reads. Trusting
    array-arrival-order as frequency-order silently misaligns every
    bin after the wrap point, comparing different real frequencies
    against each other on "repeated" measurements -- this is very
    likely the dominant cause of the phase instability investigated
    at length elsewhere in this project.

    Fix: re-index every block by its own freq_idx (mod points, to
    handle the wrap) into the correct output slot, exactly like the
    manufacturer's reference NanoVNA-Saver implementation does
    (sweepData[freqIndex] = ...), instead of trusting arrival order.
    """
    slots: list[Optional[dict]] = [None] * points
    for i in range(points):
        block = data[i * 32 : (i + 1) * 32]
        if len(block) < 32:
            break
        fwd_r, fwd_i, rev0_r, rev0_i, rev1_r, rev1_i, freq_idx = unpack_from(
            "<iiiiiihxxxxxx", block
        )
        slot = freq_idx % points  # handle wraparound explicitly
        slots[slot] = {
            "freq_idx": freq_idx,
            "fwd": complex(fwd_r, fwd_i),
            "refl": complex(rev0_r, rev0_i),
            "thru": complex(rev1_r, rev1_i),
        }

    missing = [i for i, s in enumerate(slots) if s is None]
    if missing:
        logger.warning(
            "parse_vna_data: %d/%d frequency slots never received data "
            "(missing indices: %s...) -- sweep is incomplete",
            len(missing), points, missing[:5],
        )
    # Return in TRUE frequency order (slot 0 = lowest frequency, etc),
    # regardless of what order bytes actually arrived in over serial.
    return [s for s in slots if s is not None]


@dataclass
class ConnectedDevices:
    vna_ser: object = None
    tx_ser: object = None
    rx_ser: object = None

    def close_all(self) -> None:
        for s in (self.vna_ser, self.tx_ser, self.rx_ser):
            try:
                if s and s.is_open:
                    s.close()
            except Exception:
                pass
        self.vna_ser = self.tx_ser = self.rx_ser = None