"""Capture an empty-dome baseline only after the full array has settled.

Run this with the cube removed and its support left in place:
    python capture_settled_baseline.py

This intentionally replaces data/baseline_full_sweep.json, but only after
two accepted settled captures. It does not change the VNA calibration or
the per-pair delay table.
"""
from __future__ import annotations

import json
from pathlib import Path

from capture_settled_labeled_scan import (
    MAX_RELATIVE_RMS_DIFFERENCE,
    MAX_STABILITY_ATTEMPTS,
    MIN_COMPLEX_CORRELATION,
    WARMUP_CAPTURES,
    similarity,
)


def main():
    from capture_labeled_scan import capture_one_sweep
    import scan_engine

    print("Dome must be empty. Keep the rubber support, cables and antennas fixed.")
    input("Press Enter to begin settled empty-baseline capture, or Ctrl+C to cancel: ")
    for index in range(1, WARMUP_CAPTURES + 1):
        capture_one_sweep()
        print(f"Warm-up {index}/{WARMUP_CAPTURES} complete.")

    previous = capture_one_sweep()
    accepted = None
    for attempt in range(1, MAX_STABILITY_ATTEMPTS + 1):
        current = capture_one_sweep()
        metrics = similarity(previous, current)
        print(f"Stability {attempt}/{MAX_STABILITY_ATTEMPTS}: "
              f"correlation={metrics['complex_correlation']:.6f}, "
              f"relative RMS={metrics['relative_rms_difference']:.2%}, "
              f"settled={metrics['settled']}")
        if metrics["settled"]:
            accepted = [previous, current]
            break
        previous = current
    if accepted is None:
        raise RuntimeError("The empty-device system did not settle; baseline was not replaced.")

    baseline = scan_engine.average_sweeps(accepted)
    Path("data/baseline_full_sweep.json").write_text(json.dumps(baseline))
    _, raw = scan_engine.compute_sensor_weights_from_traces(baseline)
    Path("data/baseline_raw_s21.json").write_text(json.dumps(raw, indent=2))
    print("Saved settled baseline files. VNA calibration and pair-delay calibration were unchanged.")


if __name__ == "__main__":
    main()
