"""Offline readiness and localisation report. Never opens serial hardware.

python diagnostics/localization_readiness.py
python diagnostics/localization_readiness.py --reconstruct --resolution 0.5

A complete delay table is necessary, not evidence of localisation accuracy.
Uses the current baseline and delay table; hashes make that choice explicit.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import numpy as np
from core import beamforming, calibration, geometry
from core.scan_validation import validate_full_sweep


def read(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reconstruct", action="store_true")
    parser.add_argument("--resolution", type=float, default=0.5)
    parser.add_argument("--output", type=Path, default=ROOT / "localization_readiness.json")
    args = parser.parse_args()
    if not np.isfinite(args.resolution) or args.resolution <= 0:
        parser.error("resolution must be positive and finite")
    baseline_path = ROOT / "data/baseline_full_sweep.json"
    delays_path = Path(calibration.PAIR_DELAY_CALIBRATION_FILE)
    manifest_path = ROOT / "dataset/manifest.json"
    report = {"created_at_utc": datetime.now(timezone.utc).isoformat(),
              "radius_cm": geometry.DOME_RADIUS_CM,
              "axes": "+Y RX5-8; +X 90 degrees clockwise viewed from above; +Z above base",
              "reference_policy": "current files; historical acquisition references are unverified unless snapshotted",
              "resolution_cm": args.resolution, "blockers": [], "scans": []}
    baseline, delays = None, {}
    try:
        baseline = read(baseline_path)
        report["baseline"] = {**validate_full_sweep(baseline), "sha256": digest(baseline_path)}
    except (OSError, ValueError, TypeError, KeyError) as exc:
        report["blockers"].append(f"Baseline: {exc}")
    try:
        delays = read(delays_path)
        pos = geometry.physical_antenna_positions()
        expected = {f"{tx}-{rx}" for tx in pos if tx.startswith("TX") for rx in pos if rx.startswith("RX")}
        invalid = sorted(k for k in expected if isinstance(delays.get(k), bool) or
                         not isinstance(delays.get(k), (int, float)) or not np.isfinite(delays[k]))
        report["delay_calibration"] = {"valid_pairs": len(expected)-len(invalid),
                                        "expected_pairs": len(expected), "missing_or_invalid": invalid,
                                        "sha256": digest(delays_path)}
        if invalid:
            report["blockers"].append(f"Delay calibration incomplete: {len(expected)-len(invalid)}/{len(expected)} valid pairs")
    except (OSError, ValueError, TypeError, AttributeError) as exc:
        report["blockers"].append(f"Delay calibration: {exc}")
    try:
        manifest = read(manifest_path)
    except (OSError, ValueError) as exc:
        report["blockers"].append(f"Manifest: {exc}")
        manifest = []
    for entry in manifest:
        row = {"label": entry["label"], "true_position_cm": entry["true_position_cm"]}
        try:
            path = ROOT / entry["file"].replace("\\", "/")
            sweep = read(path)
            row.update(validate_full_sweep(sweep))
            row["sha256"] = digest(path)
            row["has_reference_snapshot"] = path.with_suffix(".provenance.json").exists()
            row["usable_pairs"] = len(list(calibration.iter_usable_pairs(sweep)))
            if baseline is not None:
                calibration.subtract_baseline(sweep, baseline)
            truth = np.asarray(entry["true_position_cm"], dtype=float)
            if truth.shape != (3,) or not np.all(np.isfinite(truth)) or truth[2] < 0 or np.linalg.norm(truth) > geometry.DOME_RADIUS_CM:
                raise ValueError("Recorded target is outside the model or invalid")
            row["status"] = "blocked" if report["blockers"] else "ready_for_validation"
            if args.reconstruct and not report["blockers"]:
                row["algorithms"] = {}
                for algo in ("das", "das-cf", "dmas", "dmas-cf"):
                    result = beamforming.run_reconstruction(sweep, algo=algo, baseline_plot_data=baseline,
                                                           resolution_cm=args.resolution)
                    if not result:
                        row["algorithms"][algo] = {"status": "no_signal", "error_cm": None}
                        continue
                    pred = np.array([result[0][k] for k in ("x", "y", "z")])
                    snr = beamforming.snr_check(result)
                    row["algorithms"][algo] = {"candidate_cm": pred.tolist(),
                        "error_cm": float(np.linalg.norm(pred-truth)), "image_quality": snr,
                        "status": "candidate_requires_validation" if snr["confident"] else "inconclusive"}
        except (OSError, ValueError, TypeError, KeyError) as exc:
            row.update(status="invalid", error=str(exc))
        report["scans"].append(row)
        print(row["label"], row["status"], flush=True)
        for algo, result in row.get("algorithms", {}).items():
            print(" ", algo, result, flush=True)
    report["ready"] = not report["blockers"] and bool(report["scans"]) and all(r["status"] != "invalid" for r in report["scans"])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False))
    for blocker in report["blockers"]:
        print("BLOCKED:", blocker)
    print("Saved", args.output)
    return 0 if report["ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
