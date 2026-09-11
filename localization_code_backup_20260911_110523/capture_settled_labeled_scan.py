"""Capture a labeled scan only after full-array measurements have settled.

Usage:
    python capture_settled_labeled_scan.py <label> <x_cm> <y_cm> <z_cm>

This is intended for a target that was just placed or moved. It discards
two warm-up captures, then accepts two consecutive captures only when their
full 144-pair complex S21 data agree. The saved scan is the median of those
two accepted captures. The usual dataset manifest is updated only after the
acceptance check succeeds.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np

DATASET_DIR = "dataset"
MANIFEST_FILE = os.path.join(DATASET_DIR, "manifest.json")


WARMUP_CAPTURES = 2
MAX_STABILITY_ATTEMPTS = 6
MIN_COMPLEX_CORRELATION = 0.999
MAX_RELATIVE_RMS_DIFFERENCE = 0.03


def _complex_vector(sweep: dict) -> np.ndarray:
    """Flatten a validated full scan in deterministic pair/frequency order."""
    expected = [f"TX{tx}-RX{rx}" for tx in range(1, 13) for rx in range(1, 13)]
    values = []
    for label in expected:
        trace = sweep.get(label)
        if not trace:
            raise ValueError(f"Missing {label}")
        real = np.asarray(trace.get("s21_real", []), dtype=float)
        imag = np.asarray(trace.get("s21_imag", []), dtype=float)
        freqs = np.asarray(trace.get("freqs", []), dtype=float)
        if len(real) != 101 or len(imag) != 101 or len(freqs) != 101:
            raise ValueError(f"{label}: incomplete spectrum")
        if not np.all(np.isfinite(real)) or not np.all(np.isfinite(imag)):
            raise ValueError(f"{label}: non-finite S21")
        values.append(real + 1j * imag)
    return np.concatenate(values)


def similarity(previous: dict, current: dict) -> dict:
    """Return complex correlation and relative RMS change for two full scans."""
    a, b = _complex_vector(previous), _complex_vector(current)
    norm_a, norm_b = np.linalg.norm(a), np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        raise ValueError("Cannot evaluate stability from a zero-valued scan")
    correlation = abs(np.vdot(a, b)) / (norm_a * norm_b)
    rms_a = np.sqrt(np.mean(abs(a) ** 2))
    rms_b = np.sqrt(np.mean(abs(b) ** 2))
    relative_rms = np.sqrt(np.mean(abs(a - b) ** 2)) / ((rms_a + rms_b) / 2)
    return {
        "complex_correlation": float(correlation),
        "relative_rms_difference": float(relative_rms),
        "settled": bool(correlation >= MIN_COMPLEX_CORRELATION and
                        relative_rms <= MAX_RELATIVE_RMS_DIFFERENCE),
    }


def main():
    # These imports touch serial hardware support, so keep the pure
    # similarity helpers usable in offline tests without a connected VNA.
    from capture_labeled_scan import capture_one_sweep, print_scan_scores
    import scan_engine
    if len(sys.argv) != 5:
        print(__doc__)
        raise SystemExit(1)
    label = sys.argv[1]
    truth = [float(value) for value in sys.argv[2:]]
    print(f"Target location recorded as {truth} cm.")
    print(f"Capturing {WARMUP_CAPTURES} warm-up full scans; they will not be saved.")
    for capture_index in range(1, WARMUP_CAPTURES + 1):
        capture_one_sweep()
        print(f"Warm-up {capture_index}/{WARMUP_CAPTURES} complete.")

    previous = capture_one_sweep()
    diagnostics = []
    accepted = None
    for attempt in range(1, MAX_STABILITY_ATTEMPTS + 1):
        current = capture_one_sweep()
        metrics = similarity(previous, current)
        diagnostics.append({"attempt": attempt, **metrics})
        print(f"Stability {attempt}/{MAX_STABILITY_ATTEMPTS}: "
              f"correlation={metrics['complex_correlation']:.6f}, "
              f"relative RMS={metrics['relative_rms_difference']:.2%}, "
              f"settled={metrics['settled']}")
        if metrics["settled"]:
            accepted = [previous, current]
            break
        previous = current
    if accepted is None:
        raise RuntimeError("The system did not settle. Do not use this location measurement.")

    result = scan_engine.average_sweeps(accepted)
    os.makedirs(DATASET_DIR, exist_ok=True)
    safe_label = label.replace(" ", "_").replace("/", "_")
    scan_file = Path(DATASET_DIR) / f"{safe_label}.json"
    scan_file.write_text(json.dumps(result))
    Path(DATASET_DIR, f"{safe_label}_settling.json").write_text(json.dumps({
        "warmup_captures": WARMUP_CAPTURES,
        "stability_thresholds": {
            "min_complex_correlation": MIN_COMPLEX_CORRELATION,
            "max_relative_rms_difference": MAX_RELATIVE_RMS_DIFFERENCE,
        },
        "diagnostics": diagnostics,
    }, indent=2))

    manifest = json.loads(Path(MANIFEST_FILE).read_text()) if os.path.exists(MANIFEST_FILE) else []
    manifest = [entry for entry in manifest if entry["label"] != label]
    manifest.append({"label": label, "file": str(scan_file), "true_position_cm": truth})
    Path(MANIFEST_FILE).write_text(json.dumps(manifest, indent=2))
    print(f"Saved settled scan to {scan_file}")
    print_scan_scores(result)


if __name__ == "__main__":
    main()
