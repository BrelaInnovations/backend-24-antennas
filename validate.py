"""
validate.py -- runs DAS, DAS-CF, DMAS, and DMAS-CF against every labeled
scan in dataset/manifest.json (built by capture_labeled_scan.py) and
reports real localization error in cm against each scan's true position,
so you can see which algorithm to actually trust and by how much margin.

IMPORTANT: re-capture data/baseline_full_sweep.json (empty dome) right
before your labeled-data session, and confirm it's stable first --
see the "baseline drift" check discussed earlier. A stale baseline will
make every algorithm look wrong regardless of which one is actually
best.

Usage:
    python validate.py
    python validate.py --resolution 0.25       # finer grid, slower
    python validate.py --permittivity 1.0       # air (default); use the
                                                  # tissue value once you
                                                  # move to phantom testing
"""
import argparse
import json
import os
import sys

import numpy as np

from core import beamforming

DATASET_DIR = "dataset"
MANIFEST_FILE = os.path.join(DATASET_DIR, "manifest.json")
BASELINE_FILE = os.path.join("data", "baseline_full_sweep.json")

ALGORITHMS = ["das", "das-cf", "dmas", "dmas-cf"]
TOLERANCE_THRESHOLDS_CM = [1.0, 2.0, 3.0, 5.0]


def load_manifest():
    if not os.path.exists(MANIFEST_FILE):
        print(f"No {MANIFEST_FILE} found. Run capture_labeled_scan.py at least a few "
              f"times first (different target positions) to build a dataset.")
        sys.exit(1)
    with open(MANIFEST_FILE) as f:
        return json.load(f)


def load_baseline():
    if not os.path.exists(BASELINE_FILE):
        print(f"WARNING: no baseline file at {BASELINE_FILE} -- running WITHOUT "
              f"baseline subtraction. Results will likely be dominated by clutter.")
        return None
    with open(BASELINE_FILE) as f:
        return json.load(f)


def euclidean_error(result, true_position_cm):
    tx, ty, tz = true_position_cm
    return float(np.sqrt((result["x"] - tx) ** 2 + (result["y"] - ty) ** 2 + (result["z"] - tz) ** 2))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--resolution", type=float, default=0.5)
    parser.add_argument("--permittivity", type=float, default=1.0)
    args = parser.parse_args()

    manifest = load_manifest()
    baseline = load_baseline()

    print(f"Validating against {len(manifest)} labeled scan(s), "
          f"resolution={args.resolution}cm, permittivity={args.permittivity}\n")

    # errors[algo] = list of per-scan errors (cm)
    errors = {algo: [] for algo in ALGORITHMS}
    confident_counts = {algo: 0 for algo in ALGORITHMS}
    per_scan_rows = []

    for entry in manifest:
        label = entry["label"]
        true_pos = entry["true_position_cm"]
        with open(entry["file"]) as f:
            sweep_plot_data = json.load(f)

        row = {"label": label, "true_position_cm": true_pos}
        for algo in ALGORITHMS:
            results = beamforming.run_reconstruction(
                sweep_plot_data, algo=algo,
                resolution_cm=args.resolution, permittivity=args.permittivity,
                baseline_plot_data=baseline,
            )
            if not results:
                print(f"  [{label}] {algo}: no usable pairs / no result")
                errors[algo].append(float("inf"))
                continue

            err_cm = euclidean_error(results[0], true_pos)
            errors[algo].append(err_cm)
            snr = beamforming.snr_check(results)
            if snr["confident"]:
                confident_counts[algo] += 1

            row[algo] = {
                "predicted": (results[0]["x"], results[0]["y"], results[0]["z"]),
                "error_cm": round(err_cm, 2),
                "confident": snr["confident"],
            }
            print(f"  [{label}] {algo:8s}: predicted={row[algo]['predicted']}  "
                  f"error={err_cm:.2f}cm  confident={snr['confident']}")
        per_scan_rows.append(row)
        print()

    print("=" * 78)
    print(f"{'algorithm':10s} {'mean_cm':>8s} {'median_cm':>10s} {'max_cm':>8s} "
          + "".join(f'  <{t}cm' for t in TOLERANCE_THRESHOLDS_CM) + "   confident/N")
    for algo in ALGORITHMS:
        vals = np.array([e for e in errors[algo] if np.isfinite(e)])
        if len(vals) == 0:
            print(f"{algo:10s} -- no valid results --")
            continue
        tol_str = "".join(
            f"{100*np.mean(vals <= t):6.0f}%" for t in TOLERANCE_THRESHOLDS_CM
        )
        print(f"{algo:10s} {vals.mean():8.2f} {np.median(vals):10.2f} {vals.max():8.2f}   "
              f"{tol_str}   {confident_counts[algo]}/{len(manifest)}")

    best = min(ALGORITHMS, key=lambda a: np.mean([e for e in errors[a] if np.isfinite(e)])
               if any(np.isfinite(e) for e in errors[a]) else float("inf"))
    print()
    print(f"Lowest mean error: {best}")
    print("(Also weigh the 'confident/N' column -- an algorithm that's accurate but rarely")
    print(" confident, per snr_check(), is less useful in practice than one that's slightly")
    print(" less accurate but reliably confident.)")

    with open("validation_report.json", "w") as f:
        json.dump({"per_scan": per_scan_rows,
                    "summary": {algo: {"mean_cm": float(np.mean([e for e in errors[algo] if np.isfinite(e)]))
                                         if any(np.isfinite(e) for e in errors[algo]) else None,
                                        "confident_count": confident_counts[algo]}
                                for algo in ALGORITHMS}}, f, indent=2)
    print("\nFull per-scan detail saved to validation_report.json")


if __name__ == "__main__":
    main()
