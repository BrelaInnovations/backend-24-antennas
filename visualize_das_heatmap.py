"""
visualize_das_heatmap.py -- matplotlib thermal-map visualization of a
DAS/DMAS-CF reconstruction, generated entirely in the backend (no React
frontend needed). Produces one PNG with two panels:

  1. Top-down overview -- x/y plane, collapsing all depths together
     (each x/y cell shows its MAX intensity across every z it has a
     voxel at). Good for "where, roughly, is the hot region".
  2. Peak-depth slice -- x/y plane at the SAME z as the reconstruction's
     single strongest voxel only. Good for seeing how tight/diffuse the
     hot region actually is at the depth that matters, without the
     top-down view's across-all-depths blurring.

Antenna positions (from core.geometry.physical_antenna_positions()) are
overlaid on both panels as a spatial reference. The reconstructed candidate
is marked with a white star. For a file listed in dataset/manifest.json, its
recorded true location is marked with a blue X for direct comparison.

Run this against any previously saved capture -- either a labeled scan
from capture_labeled_scan.py (dataset/<label>.json) or the empty-dome
baseline itself (data/baseline_full_sweep.json, useful as a "what does
the noise floor look like" reference).

Usage:
    python visualize_das_heatmap.py <path_to_sweep_json> [algo]
    python visualize_das_heatmap.py <path_to_sweep_json> [algo] --true X Y Z

    <path_to_sweep_json>  e.g. dataset/metaltest1_.json
    [algo]                das | das-cf | dmas | dmas-cf (default: dmas-cf,
                          matching what the real app uses for dots)

Examples:
    python visualize_das_heatmap.py dataset/metaltest1_.json
    python visualize_das_heatmap.py dataset/metaltest1_.json das-cf
    python visualize_das_heatmap.py data/baseline_full_sweep.json
    python visualize_das_heatmap.py dataset/new_scan.json dmas-cf --true 2 2 2.5
"""
import json
import os
import sys
from datetime import datetime

import numpy as np
import matplotlib.pyplot as plt

from core import geometry
from core.beamforming import run_reconstruction, snr_check

BASELINE_FILE = os.path.join("data", "baseline_full_sweep.json")
MANIFEST_FILE = os.path.join("dataset", "manifest.json")


def load_sweep(path: str) -> dict:
    with open(path) as f:
        return json.load(f)


def _normalized_path(path: str) -> str:
    """Compare manifest paths consistently across Windows slash styles."""
    return os.path.normcase(os.path.abspath(os.path.normpath(path)))


def true_position_from_manifest(sweep_path: str):
    """Return recorded [x, y, z] for a dataset file, or None if unlabeled."""
    if not os.path.exists(MANIFEST_FILE):
        return None
    with open(MANIFEST_FILE) as f:
        entries = json.load(f)
    target = _normalized_path(sweep_path)
    for entry in entries:
        file_path = entry.get("file")
        position = entry.get("true_position_cm")
        if not file_path or not isinstance(position, list) or len(position) != 3:
            continue
        if _normalized_path(file_path) == target:
            return tuple(float(value) for value in position)
    return None


def to_grid(results: list[dict], z_filter=None):
    """results -> (xs, ys, grid) where grid[i,j] is the intensity at
    (xs[j], ys[i]), taking the MAX over z when z_filter is None (top-down
    collapse), or restricted to voxels matching z_filter (a single-depth
    slice) otherwise. Cells with no matching voxel are NaN (renders
    transparent/blank rather than misleadingly "zero")."""
    if z_filter is not None:
        results = [r for r in results if abs(r["z"] - z_filter) < 1e-6]

    xs = sorted({round(r["x"], 3) for r in results})
    ys = sorted({round(r["y"], 3) for r in results})
    x_idx = {x: i for i, x in enumerate(xs)}
    y_idx = {y: i for i, y in enumerate(ys)}

    grid = np.full((len(ys), len(xs)), np.nan)
    for r in results:
        i = y_idx[round(r["y"], 3)]
        j = x_idx[round(r["x"], 3)]
        if np.isnan(grid[i, j]) or r["intensity"] > grid[i, j]:
            grid[i, j] = r["intensity"]
    return np.array(xs), np.array(ys), grid


def overlay_antennas(ax):
    positions = geometry.physical_antenna_positions()
    for label, (x, y, z) in positions.items():
        color = "cyan" if label.startswith("TX") else "lime"
        marker = "^" if label.startswith("TX") else "o"
        ax.scatter([x], [y], c=color, marker=marker, s=40, edgecolors="black",
                   linewidths=0.5, zorder=5)
        ax.annotate(label, (x, y), fontsize=7, color="white",
                    xytext=(4 if x >= 0 else -4, 4), textcoords="offset points",
                    ha="left" if x >= 0 else "right",
                    bbox=dict(facecolor="black", alpha=0.7, edgecolor="none", pad=1),
                    zorder=6)


def plot_panel(ax, xs, ys, grid, title, peak_xy=None, true_xy=None):
    if len(xs) < 2 or len(ys) < 2:
        ax.set_title(f"{title}\n(not enough points to render)")
        return
    # imshow expects pixel EDGES, whereas xs/ys contain voxel CENTERS.
    dx, dy = xs[1] - xs[0], ys[1] - ys[0]
    extent = [xs.min()-dx/2, xs.max()+dx/2, ys.min()-dy/2, ys.max()+dy/2]
    im = ax.imshow(grid, extent=extent, origin="lower", cmap="inferno",
                    aspect="equal", interpolation="nearest")
    plt.colorbar(im, ax=ax, label="intensity", fraction=0.046, pad=0.04)
    overlay_antennas(ax)
    if peak_xy is not None:
        ax.scatter([peak_xy[0]], [peak_xy[1]], marker="*", s=250,
                   c="white", edgecolors="black", linewidths=1, zorder=10,
                   label="candidate peak")
        ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.12), fontsize=7)
    if true_xy is not None:
        ax.scatter([true_xy[0]], [true_xy[1]], marker="x", s=135,
                   c="deepskyblue", linewidths=3, zorder=11,
                   label="recorded true location")
        ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.12), fontsize=7)
    radius = geometry.DOME_RADIUS_CM
    ax.set_xlim(-radius-0.75, radius+0.75)
    ax.set_ylim(-radius-0.75, radius+0.75)
    ax.axhline(0, color="gray", linewidth=0.6, linestyle=":")
    ax.axvline(0, color="gray", linewidth=0.6, linestyle=":")
    ax.set_xlabel("x (cm); +X between RX1 and TX9")
    ax.set_ylabel("y (cm); +Y toward RX5-8")
    ax.set_title(title)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    sweep_path = sys.argv[1]
    remaining = sys.argv[2:]
    algo = "dmas-cf"
    if remaining and remaining[0] != "--true":
        algo = remaining.pop(0)
    true_position = true_position_from_manifest(sweep_path)
    if remaining:
        if len(remaining) != 4 or remaining[0] != "--true":
            raise SystemExit("Use --true X Y Z after the optional algorithm name.")
        try:
            true_position = tuple(float(value) for value in remaining[1:])
        except ValueError as exc:
            raise SystemExit("True coordinates must be numeric values in cm.") from exc

    sweep = load_sweep(sweep_path)

    from core.reference_snapshot import load_reference_snapshot
    saved_references = load_reference_snapshot(sweep_path)
    pair_delays = None
    baseline = None
    if saved_references is not None:
        baseline = saved_references["baseline"]
        pair_delays = saved_references["delays"]
        print("Using recorded baseline and delay calibration:", saved_references["session"])
    elif os.path.exists(BASELINE_FILE) and os.path.abspath(sweep_path) != os.path.abspath(BASELINE_FILE):
        with open(BASELINE_FILE) as f:
            baseline = json.load(f)
    elif os.path.abspath(sweep_path) == os.path.abspath(BASELINE_FILE):
        print("Visualizing the baseline file itself -- no baseline subtraction applied "
              "(this shows the raw noise floor, not a delta).")
    else:
        print(f"WARNING: no baseline found at {BASELINE_FILE} -- reconstructing "
              f"WITHOUT baseline subtraction. Results will look very different from "
              f"real scans, which always subtract baseline first.")

    if saved_references is None:
        print("No target reference snapshot: using current references; historical comparability is unverified.")
    print(f"Running {algo} reconstruction ...")
    results = run_reconstruction(sweep, algo=algo, baseline_plot_data=baseline,
                                 pair_delay_calibration=pair_delays)

    if not results:
        print("No reconstruction result -- check the sweep file has usable pairs.")
        sys.exit(1)

    peak = results[0]
    confidence = snr_check(results)
    print(f"\nPeak: x={peak['x']:.2f} y={peak['y']:.2f} z={peak['z']:.2f} "
          f"intensity={peak['intensity']!r} coherence={peak['coherence']:.4f}")
    print(f"Confidence: {confidence}")
    error_cm = None
    if true_position is not None:
        error_cm = float(np.linalg.norm(np.asarray((peak["x"], peak["y"], peak["z"])) - true_position))
        print("Recorded true location: "
              f"x={true_position[0]:.2f} y={true_position[1]:.2f} z={true_position[2]:.2f} cm")
        print(f"Candidate-to-true 3D error: {error_cm:.2f} cm")

    xs_top, ys_top, grid_top = to_grid(results, z_filter=None)
    xs_slice, ys_slice, grid_slice = to_grid(results, z_filter=peak["z"])

    fig, axes = plt.subplots(1, 2, figsize=(13, 5.5))
    fig.suptitle(
        f"{os.path.basename(sweep_path)} -- {algo} -- "
        f"confident={confidence['confident']} "
        f"(ratio={confidence['peak_to_mean_ratio']}, coherence={confidence['coherence']:.3f})"
        + (f" — recorded-location error={error_cm:.2f} cm" if error_cm is not None else "")
    )
    plot_panel(axes[0], xs_top, ys_top, grid_top,
               "Top-down overview (max intensity across all depths)",
               peak_xy=(peak["x"], peak["y"]),
               true_xy=true_position[:2] if true_position is not None else None)
    plot_panel(axes[1], xs_slice, ys_slice, grid_slice,
               f"Slice at peak depth (z={peak['z']:.2f} cm)",
               peak_xy=(peak["x"], peak["y"]),
               true_xy=true_position[:2] if true_position is not None else None)
    fig.tight_layout()

    out_dir = "heatmaps"
    os.makedirs(out_dir, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = os.path.splitext(os.path.basename(sweep_path))[0]
    out_path = os.path.join(out_dir, f"{base}_{algo}_{stamp}.png")
    fig.savefig(out_path, dpi=150)
    print(f"\nSaved heatmap to {out_path}")

    try:
        plt.show()
    except Exception:
        print("(Could not open an interactive window -- open the saved PNG instead.)")


if __name__ == "__main__":
    main()
