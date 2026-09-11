"""
calibration.py -- per-pair system delay table, baseline subtraction, and
the two validated pair-exclusion lists (same-index pairs, phase-unstable
pairs). All measured empirically -- see measure_system_delay_full.py and
check_phase_stability_full.py in the diagnostics/ folder to re-derive
these if hardware changes (new cables, reseated connectors, etc).
"""
from __future__ import annotations
import json
import os
from typing import Dict, Optional

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
PAIR_DELAY_CALIBRATION_FILE = os.path.join(DATA_DIR, "pair_delay_calibration.json")
PHASE_STABILITY_RESULTS_FILE = os.path.join(DATA_DIR, "phase_stability_results.json")
WEAK_BASELINE_PAIRS_FILE = os.path.join(DATA_DIR, "weak_baseline_pairs.json")

# ---- Exclusion toggles (each independently switchable for A/B testing) ----
EXCLUDE_SAME_INDEX_PAIRS = True       # validated: real, measured improvement
EXCLUDE_UNSTABLE_PHASE_PAIRS = True   # validated: real, measured improvement
EXCLUDE_WEAK_BASELINE_PAIRS = False   # tested: partial/inconclusive, left off


def load_pair_delay_calibration() -> Dict[str, float]:
    """{"TX1-RX1": delay_seconds, ...}. Missing file -> empty dict (delay 0
    for every pair) rather than crashing, so this degrades gracefully."""
    if not os.path.exists(PAIR_DELAY_CALIBRATION_FILE):
        return {}
    with open(PAIR_DELAY_CALIBRATION_FILE) as f:
        return json.load(f)


def _load_unstable_phase_pairs() -> set:
    if not EXCLUDE_UNSTABLE_PHASE_PAIRS or not os.path.exists(PHASE_STABILITY_RESULTS_FILE):
        return set()
    try:
        with open(PHASE_STABILITY_RESULTS_FILE) as f:
            data = json.load(f)
        # accept either {"unstable_pairs": [...]} or a flat list
        if isinstance(data, dict):
            return set(data.get("unstable_pairs", []))
        return set(data)
    except Exception:
        return set()


def _load_weak_baseline_pairs() -> set:
    if not EXCLUDE_WEAK_BASELINE_PAIRS or not os.path.exists(WEAK_BASELINE_PAIRS_FILE):
        return set()
    try:
        with open(WEAK_BASELINE_PAIRS_FILE) as f:
            return set(json.load(f))
    except Exception:
        return set()


def iter_usable_pairs(sweep_plot_data: dict):
    """Yields (tx, rx, label, data) for every pair surviving all exclusions."""
    weak_baseline_pairs = _load_weak_baseline_pairs()
    unstable_phase_pairs = _load_unstable_phase_pairs()

    for tx in range(1, 13):
        for rx in range(1, 13):
            if EXCLUDE_SAME_INDEX_PAIRS and tx == rx:
                continue
            label = f"TX{tx}-RX{rx}"
            if label in weak_baseline_pairs or label in unstable_phase_pairs:
                continue
            data = sweep_plot_data.get(label)
            if not data or not data.get("s21_real"):
                continue
            yield tx, rx, label, data


def subtract_baseline(sweep_plot_data: dict, baseline_plot_data: dict) -> dict:
    """
    Per TX-RX pair, per frequency point: delta = scan - baseline (complex).
    STRICT FREQUENCY-MATCH GUARD: raises instead of silently truncating
    mismatched sweeps.
    """
    import numpy as np

    result: dict = {}
    for label, scan in sweep_plot_data.items():
        baseline = baseline_plot_data.get(label)
        if not scan or not scan.get("s21_real"):
            result[label] = scan
            continue
        if not baseline or not baseline.get("s21_real"):
            raise ValueError(f"No baseline data for {label} -- cannot subtract")

        scan_freqs = np.asarray(scan["freqs"], dtype=float)
        base_freqs = np.asarray(baseline["freqs"], dtype=float)
        if len(scan_freqs) != len(base_freqs):
            raise ValueError(
                f"{label}: scan has {len(scan_freqs)} freq points but baseline has "
                f"{len(base_freqs)} -- refusing to subtract mismatched sweeps."
            )
        if not np.allclose(scan_freqs, base_freqs, rtol=1e-6):
            raise ValueError(
                f"{label}: scan and baseline freq grids don't match -- refusing to subtract."
            )

        scan_c = np.asarray(scan["s21_real"]) + 1j * np.asarray(scan["s21_imag"])
        base_c = np.asarray(baseline["s21_real"]) + 1j * np.asarray(baseline["s21_imag"])
        delta_c = scan_c - base_c
        result[label] = {
            "freqs": scan["freqs"],
            "s21_real": delta_c.real.tolist(),
            "s21_imag": delta_c.imag.tolist(),
        }
    return result
