"""
scan_engine.py — real multi-antenna sweep + scoring, ported from the legacy
Tkinter GUI's `_full_sweep_thread` and `compute_sensor_weights_from_traces`.

Two independent pieces:
  1. run_full_sweep()                 -> collects raw S21 (dB) traces for
                                          every TX-RX antenna pair.
  2. compute_sensor_weights_from_traces() -> turns those traces into a
                                          normalized 0..1 "weight" per pair,
                                          which is what colors the dome.

No GUI, no FastAPI, no Tkinter dependency -- pure functions over
hardware.py's serial primitives, so this can be unit-tested standalone
(see test_scan_engine.py) before ever touching real hardware.
"""

from __future__ import annotations

import logging
import math
from time import sleep
from typing import Callable, Optional

import numpy as np

import hardware

logger = logging.getLogger("naibra.scan_engine")


def db20(val: complex) -> float:
    """Magnitude of a complex value, in dB. Mirrors the legacy GUI's db20()."""
    mag = abs(val)
    return 20 * math.log10(mag) if mag > 1e-9 else -180.0


def process_sweep_data(sweep_data: list[dict], start_freq: int, stop_freq: int, points: int,
                        calibration=None):
    """
    Raw VNA points (fwd/refl/thru complex values) -> (freqs_ghz, s21_db, s21_complex_list).

    `calibration`, if given, is a calibration.Calibration instance (loaded
    from the .cal file that used to be manually loaded into NanoVNA-Saver
    for the legacy GUI). When present, each raw S21 is corrected with it
    before converting to dB -- this removes cable/switch-matrix leakage and
    transmission loss that would otherwise show up as "signal" even with
    nothing in the device.

    `s21_complex_list` (a list of Python complex numbers, one per frequency
    point) is returned ALONGSIDE s21_db -- the existing weight/severity
    logic only ever used magnitude (dB), but a delay-and-sum reconstruction
    needs phase too (it does an IFFT to go from frequency-domain to
    time-domain, which requires the full complex spectrum, not just |S21|).
    """
    freqs = []
    s21_db = []
    s21_complex_list = []
    step = (stop_freq - start_freq) / (points - 1)

    for point in sweep_data:
        # Use the point's OWN freq_idx to compute its true frequency,
        # rather than trusting its position in the list -- see the fix
        # in hardware.parse_vna_data() for why this matters.
        freq_hz = start_freq + point["freq_idx"] * step
        freqs.append(freq_hz / 1e9)

        s21_complex = point["thru"] / point["fwd"] if abs(point["fwd"]) > 0 else 0j
        if calibration is not None:
            s21_complex = calibration.correct_s21(freq_hz, s21_complex)
        s21_db.append(db20(s21_complex))
        s21_complex_list.append(s21_complex)

    return freqs, s21_db, s21_complex_list


def run_full_sweep(
    vna_ser,
    tx_ser,
    rx_ser,
    start_freq: int,
    stop_freq: int,
    num_antennas: int,
    points: int = 101,
    on_progress: Optional[Callable[[str, int, int], None]] = None,
    calibration=None,
) -> dict:
    """
    Sweep every TX-RX antenna pair (num_antennas x num_antennas combinations)
    and return {"TX{n}-RX{m}": {"freqs": [...], "s21": [...]}, ...}.

    on_progress(label, completed, total) is called after each pair, if given
    -- useful for streaming progress to the frontend later.

    `calibration`, if given, is passed straight through to
    process_sweep_data() to correct each pair's S21 using the .cal file
    (see calibration.py).
    """
    sweep_plot_data: dict = {}
    total = num_antennas * num_antennas
    completed = 0

    for tx in range(1, num_antennas + 1):
        for rx in range(1, num_antennas + 1):
            label = f"TX{tx}-RX{rx}"
            try:
                hardware.send_switch_command(tx_ser, hardware.format_switch_command(tx))
                hardware.send_switch_command(rx_ser, hardware.format_switch_command(rx))
                # NOTE: was 0.00004s (40 microseconds) -- "matches legacy GUI
                # timing" but that's almost certainly too short for real
                # switch settling (mechanical relays typically need 5-20ms;
                # even solid-state RF switches often need low-single-digit
                # ms). Testing 0.01s (10ms) as the first hypothesis for the
                # widespread phase instability seen across ~half the array.
                # If check_phase_stability_full.py's unstable count drops
                # significantly, this was a major contributor. Tune from
                # here -- try 0.005, 0.02, 0.05 to find the actual minimum
                # needed for YOUR specific switch hardware.
                sleep(0.01)

                hardware.set_vna_sweep(vna_ser, start_freq, stop_freq, points)
                sleep(0.1)
                hardware.clear_vna_fifo(vna_ser)
                raw = hardware.read_vna_data(vna_ser, points)
                sweep_data = hardware.parse_vna_data(raw, points)

                freqs, s21_db, s21_complex_list = process_sweep_data(
                    sweep_data, start_freq, stop_freq, points, calibration=calibration)
                # store real/imag separately -- Python complex isn't
                # JSON-serializable, and this dict eventually goes into a
                # FastAPI/Mongo response.
                sweep_plot_data[label] = {
                    "freqs": freqs,
                    "s21": s21_db,
                    "s21_real": [c.real for c in s21_complex_list],
                    "s21_imag": [c.imag for c in s21_complex_list],
                }
            except Exception as e:
                logger.exception("Sweep failed for %s", label)
                sweep_plot_data[label] = {"freqs": [], "s21": [], "s21_real": [], "s21_imag": [], "error": str(e)}

            completed += 1
            if on_progress:
                on_progress(label, completed, total)

    hardware.send_switch_command(tx_ser, "OFF;")
    hardware.send_switch_command(rx_ser, "OFF;")
    return sweep_plot_data


def compute_sensor_weights_from_traces(sweep_plot_data: dict) -> tuple[dict, dict]:
    """
    Direct port of the legacy GUI's compute_sensor_weights_from_traces().

    For each TX-RX pair, average its S21 (dB) across the sweep. Then
    normalize all pairs' averages globally into a 0..1 "weight" -- this is
    what the dome visualization colors/dots are driven by.

    Returns (weights, raw_values), both keyed by "TX{n}-RX{m}".
    """
    weights: dict = {}
    raw_values: dict = {}

    if not sweep_plot_data:
        return weights, raw_values

    all_s21_values: list[float] = []
    temp_averages: dict = {}

    for label, data in sweep_plot_data.items():
        s21 = data.get("s21")
        if s21:
            avg_s21 = float(np.mean(s21))
            temp_averages[label] = avg_s21
            all_s21_values.extend(s21)

    if all_s21_values and temp_averages:
        global_min = min(all_s21_values)
        global_max = max(all_s21_values)
        global_range = global_max - global_min if global_max != global_min else 1

        for label, avg_s21 in temp_averages.items():
            weight = (avg_s21 - global_min) / global_range
            weights[label] = max(0.0, min(1.0, weight))
            raw_values[label] = avg_s21

    return weights, raw_values

def average_sweeps(sweep_results_list: list[dict]) -> dict:
    """
    Combine multiple run_full_sweep() results together, per TX-RX pair,
    per frequency bin, using the MEDIAN (not mean) across sweeps.

    Median instead of mean because occasional per-sweep glitches (e.g.
    switch-relay contact bounce, a transient serial-timing hiccup) show up
    as one sweep's value being wildly different from the rest, even though
    the others agree closely -- a mean lets that one bad sweep skew the
    result, while a median simply ignores it as long as most sweeps agree.
    """
    import numpy as np

    if not sweep_results_list:
        return {}
    if len(sweep_results_list) == 1:
        return sweep_results_list[0]

    labels = sweep_results_list[0].keys()
    averaged: dict = {}
    for label in labels:
        entries = [s[label] for s in sweep_results_list
                   if label in s and s[label].get("s21_real")]
        if not entries:
            averaged[label] = {"freqs": [], "s21": [], "s21_real": [], "s21_imag": []}
            continue
        n = min(len(e["s21_real"]) for e in entries)

        real_arr = np.array([e["s21_real"][:n] for e in entries])  # (num_sweeps, n)
        imag_arr = np.array([e["s21_imag"][:n] for e in entries])
        # NOTE: median is taken independently per real/imag component --
        # this is a standard, simple choice, though it can occasionally
        # produce a combined (real,imag) pair that isn't exactly any single
        # sweep's actual complex value. Good enough for outlier rejection.
        s21_real_med = np.median(real_arr, axis=0).tolist()
        s21_imag_med = np.median(imag_arr, axis=0).tolist()

        s21_lists = [e.get("s21", [])[:n] for e in entries if e.get("s21")]
        if s21_lists:
            m = min(len(x) for x in s21_lists)
            s21_db_med = np.median(np.array([x[:m] for x in s21_lists]), axis=0).tolist()
        else:
            s21_db_med = []

        averaged[label] = {
            "freqs": entries[0]["freqs"][:n],
            "s21": s21_db_med,
            "s21_real": s21_real_med,
            "s21_imag": s21_imag_med,
        }
    return averaged