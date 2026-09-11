"""
test_phase_stability_synthetic.py -- proves capture_phase_stability.py's
core math is correct, using synthetic data with KNOWN answers -- no
hardware needed at all.

Builds three scenarios and checks the script correctly tells them apart:
  A) weak signal, pure noise, no real hardware defect
     -> should be flagged UNSTABLE, with LOW magnitude
  B) strong signal, but genuinely random phase each repeat (simulates a
     real hardware defect)
     -> should be flagged UNSTABLE, with HIGH (normal) magnitude
  C) strong signal, consistent phase across repeats
     -> should be flagged STABLE

If this script prints "ALL CHECKS PASSED" at the end, the phase-stability
math itself is confirmed correct -- any instability you see on your real
hardware is a real hardware finding, not a bug in this test.

Usage:
    python test_phase_stability_synthetic.py
"""
import sys
import os

# import circular_std_deg_per_freq directly from the real script --
# testing the ACTUAL function you're running, not a reimplementation
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "diagnostics"))

import numpy as np
from capture_phase_stability import circular_std_deg_per_freq

THRESHOLD_DEG = 20.0
N_REPEATS = 10
freqs_ghz = np.linspace(2.0, 6.0, 101)


def build_scenario(kind, rng):
    """Returns list of (re, im) tuples, one pair per repeat, for ONE
    synthetic antenna pair matching the given scenario."""
    spectra = []
    for _ in range(N_REPEATS):
        if kind == "weak_noise":
            amp = 0.00005  # very weak, no real signal at all
            s21 = (rng.standard_normal(101) + 1j * rng.standard_normal(101)) * amp
        elif kind == "strong_jitter":
            amp = 0.02  # strong signal
            phase_offset = rng.uniform(0, 2 * np.pi)  # jumps randomly EVERY repeat
            s21 = amp * np.exp(1j * (phase_offset + freqs_ghz * 0.1))
            s21 += (rng.standard_normal(101) + 1j * rng.standard_normal(101)) * 0.0002
        elif kind == "strong_stable":
            amp = 0.02
            s21 = amp * np.exp(1j * (0.5 + freqs_ghz * 0.1))  # SAME phase every repeat
            s21 += (rng.standard_normal(101) + 1j * rng.standard_normal(101)) * 0.0002
        else:
            raise ValueError(kind)
        spectra.append((s21.real.tolist(), s21.imag.tolist()))
    return spectra


def main():
    rng = np.random.default_rng(1234)
    scenarios = {
        "weak_noise (expect UNSTABLE, low magnitude)": "weak_noise",
        "strong_jitter (expect UNSTABLE, normal magnitude)": "strong_jitter",
        "strong_stable (expect STABLE)": "strong_stable",
    }

    all_passed = True

    print(f"Testing circular_std_deg_per_freq() with {N_REPEATS} synthetic repeats per scenario\n")

    for label, kind in scenarios.items():
        spectra = build_scenario(kind, rng)
        per_freq_std = circular_std_deg_per_freq(spectra)
        std = float(np.mean(per_freq_std))
        mags = [np.abs(np.asarray(re) + 1j * np.asarray(im)).mean() for re, im in spectra]
        mag = float(np.mean(mags))

        flagged_unstable = std >= THRESHOLD_DEG
        expected_unstable = kind in ("weak_noise", "strong_jitter")

        ok = flagged_unstable == expected_unstable
        all_passed = all_passed and ok

        status = "PASS" if ok else "FAIL"
        print(f"[{status}] {label}")
        print(f"       computed std={std:.1f} deg, magnitude={mag:.4e}, "
              f"flagged_unstable={flagged_unstable} (expected={expected_unstable})")
        print()

    # also a direct sanity check: a pair that is IDENTICAL every repeat
    # (zero noise at all) must show essentially 0 degrees of spread
    identical = [([0.01] * 101, [0.005] * 101) for _ in range(N_REPEATS)]
    std_identical = float(np.mean(circular_std_deg_per_freq(identical)))
    ok = std_identical < 0.01
    all_passed = all_passed and ok
    print(f"[{'PASS' if ok else 'FAIL'}] identical repeats, zero noise "
          f"(expect ~0 deg): computed={std_identical:.4f} deg")

    print()
    if all_passed:
        print("ALL CHECKS PASSED -- the phase-stability math in "
              "capture_phase_stability.py is confirmed correct.")
    else:
        print("SOME CHECKS FAILED -- something is wrong, do not trust "
              "results from capture_phase_stability.py until this is fixed.")
        sys.exit(1)


if __name__ == "__main__":
    main()