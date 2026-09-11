"""
capture_phase_stability.py -- measures per-pair phase stability across
repeated empty-device sweeps, and writes detailed per-frequency diagnostics.

IMPORTANT:
  - Acquisition is unchanged: still uses capture_one_sweep().
  - The script now saves, for every TX/RX pair and frequency bin:
      * mean |S21| across repeats
      * circular phase standard deviation
  - This lets us determine whether large phase variation occurs mainly
    where S21 is weak.

Usage:
    python capture_phase_stability.py
    python capture_phase_stability.py --repeats 10 --threshold 20
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse
import json
from pathlib import Path

import numpy as np

from capture_labeled_scan import capture_one_sweep


OUT_PATH = Path("data/phase_stability_results.json")


def run_one_sweep(label: str) -> dict:
    print(f"Capturing scan (label={label!r}) directly from hardware ...")
    sweep = capture_one_sweep()

    if not sweep:
        raise RuntimeError(
            "capture_one_sweep() returned no data -- check hardware is connected."
        )

    return sweep


def circular_std_deg_per_freq(spectra: list) -> np.ndarray:
    """
    spectra:
        list of (re, im) arrays for ONE TX/RX pair,
        one pair of arrays per repeat.

    Returns:
        Circular phase standard deviation in degrees at every
        frequency bin.
    """
    stack = np.array([
        np.asarray(re) + 1j * np.asarray(im)
        for re, im in spectra
    ])

    phases = np.angle(stack)

    R = np.clip(
        np.abs(np.mean(np.exp(1j * phases), axis=0)),
        1e-9,
        1.0,
    )

    return np.degrees(np.sqrt(-2 * np.log(R)))


def mean_magnitude_per_freq(spectra: list) -> np.ndarray:
    """
    Return mean |S21| across repeats at every frequency bin.
    """
    magnitudes = np.array([
        np.abs(np.asarray(re) + 1j * np.asarray(im))
        for re, im in spectra
    ])

    return np.mean(magnitudes, axis=0)


def main():
    ap = argparse.ArgumentParser()

    ap.add_argument(
        "--repeats",
        type=int,
        default=10,
        help="number of repeated empty-device sweeps",
    )

    ap.add_argument(
        "--threshold",
        type=float,
        default=20.0,
        help="mean per-frequency circular std above which a pair is unstable",
    )

    args = ap.parse_args()

    if args.repeats < 1:
        raise ValueError("--repeats must be >= 1")

    print(
        f"Running {args.repeats} repeat sweeps on the EMPTY device "
        "-- do not touch/reconnect anything."
    )

    # all_spectra[pair] =
    #   list of (re_array, im_array) tuples, one per repeat
    all_spectra: dict = {}

    # Store frequency grid for each pair.
    frequency_grids: dict = {}

    for i in range(args.repeats):
        print(
            f"  sweep {i + 1}/{args.repeats}...",
            end=" ",
            flush=True,
        )

        sweep = run_one_sweep(f"phase-stability-{i + 1}")

        for pair, data in sweep.items():
            re = data.get("s21_real")
            im = data.get("s21_imag")
            freqs = data.get("freqs")

            if (
                not re
                or not im
                or len(re) != len(im)
                or not freqs
                or len(freqs) != len(re)
            ):
                continue

            all_spectra.setdefault(pair, []).append((re, im))

            # Keep the frequency grid from the first valid repeat.
            if pair not in frequency_grids:
                frequency_grids[pair] = freqs

        print("done")

    results = {}
    unstable_pairs = []
    magnitudes = {}
    per_frequency = {}

    for pair, spectra in all_spectra.items():

        if len(spectra) < max(2, (args.repeats + 1) // 2):
            continue

        # ------------------------------------------------------------
        # Phase standard deviation at EVERY frequency bin
        # ------------------------------------------------------------
        per_freq_std = circular_std_deg_per_freq(spectra)

        # ------------------------------------------------------------
        # Mean |S21| at EVERY frequency bin
        # ------------------------------------------------------------
        per_freq_mag = mean_magnitude_per_freq(spectra)

        # Existing scalar metric is preserved:
        # mean phase std across all frequency bins.
        std = float(np.mean(per_freq_std))

        results[pair] = round(std, 1)

        # Existing pair-level average magnitude is also preserved.
        magnitudes[pair] = float(np.mean(per_freq_mag))

        # ------------------------------------------------------------
        # Save detailed frequency-by-frequency diagnostic data
        # ------------------------------------------------------------
        freqs = frequency_grids.get(pair, [])

        n = min(
            len(freqs),
            len(per_freq_std),
            len(per_freq_mag),
        )

        per_frequency[pair] = {
            "freqs_ghz": [
                float(x) for x in freqs[:n]
            ],
            "mean_abs_s21": [
                float(x) for x in per_freq_mag[:n]
            ],
            "phase_std_deg": [
                float(x) for x in per_freq_std[:n]
            ],
        }

        if std >= args.threshold:
            unstable_pairs.append(pair)

    unstable_pairs.sort()

    # ------------------------------------------------------------
    # Pair-level correlation
    # ------------------------------------------------------------
    corr = None

    stds_arr = np.array([
        results[p] for p in results
    ])

    mags_arr = np.array([
        magnitudes[p] for p in results
    ])

    if len(stds_arr) > 2:
        corr = float(
            np.corrcoef(
                stds_arr,
                np.log10(mags_arr + 1e-12),
            )[0, 1]
        )

    # ------------------------------------------------------------
    # Save everything
    # ------------------------------------------------------------
    out = {
        "unstable_pairs": unstable_pairs,
        "threshold_deg": args.threshold,
        "repeats": args.repeats,

        # Existing scalar results
        "per_pair_std_deg": results,
        "per_pair_mean_abs_s21": magnitudes,

        # New diagnostic data
        "per_frequency": per_frequency,

        # Existing correlation diagnostic
        "correlation_phase_std_vs_log10_mean_abs_s21": corr,
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    OUT_PATH.write_text(
        json.dumps(out, indent=2)
    )

    # ------------------------------------------------------------
    # Terminal summary
    # ------------------------------------------------------------
    print()

    print(
        f"Wrote {OUT_PATH} -- "
        f"{len(unstable_pairs)}/{len(results)} pairs flagged unstable "
        f"(>= {args.threshold} deg mean spread)"
    )

    print()

    print(
        "Per-pair spread (sorted worst to best), "
        "with average |S21| magnitude:"
    )

    for pair, std in sorted(
        results.items(),
        key=lambda kv: -kv[1],
    ):
        flag = (
            "  <-- UNSTABLE"
            if std >= args.threshold
            else ""
        )

        print(
            f"  {pair:12s} "
            f"{std:6.1f} deg   "
            f"mag={magnitudes[pair]:.4e}"
            f"{flag}"
        )

    if corr is not None:
        print()
        print(
            "Correlation between phase-std and log(magnitude) "
            f"across all pairs: {corr:.3f}"
        )

    # ------------------------------------------------------------
    # Print detailed information for the worst 5 pairs
    # ------------------------------------------------------------
    print()
    print("Worst 5 pairs -- frequency-by-frequency diagnostic:")

    worst_pairs = sorted(
        results,
        key=lambda p: results[p],
        reverse=True,
    )[:5]

    for pair in worst_pairs:
        data = per_frequency[pair]

        print()
        print(
            f"{pair}: overall phase std = "
            f"{results[pair]:.1f} deg"
        )

        print(
            f"{'Freq(GHz)':>10s} "
            f"{'|S21|':>12s} "
            f"{'PhaseStd(deg)':>15s}"
        )

        print("-" * 40)

        for f, mag, phase_std in zip(
            data["freqs_ghz"],
            data["mean_abs_s21"],
            data["phase_std_deg"],
        ):
            print(
                f"{f:10.3f} "
                f"{mag:12.5e} "
                f"{phase_std:15.2f}"
            )


if __name__ == "__main__":
    main()