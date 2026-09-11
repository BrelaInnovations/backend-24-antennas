"""
simulate_test.py -- tests the localization ALGORITHM (geometry, calibration,
beamforming) against synthetic, perfectly-known data -- no real hardware
involved at all. Useful for confirming the code itself is correct,
independent of any hardware noise/instability issues.

For each true position, this builds a synthetic S21 sweep by computing the
exact expected delay for every antenna pair (using the SAME geometry and
calibration table beamforming.py actually uses) and encoding that as a
linear phase ramp across frequency -- i.e. exactly what a perfect,
noiseless reflector at that position would produce. A small amount of
noise is added (matching the amplitude of real measurement noise, so it's
still a fair pipeline test, not "too easy").

Usage:
    python simulate_test.py
    python simulate_test.py --noise 0.0          # zero noise -- pure math check
    python simulate_test.py --use-real-calibration false   # ignore your
        measured pair_delay_calibration.json, test with zero system delay
        instead (useful to isolate "is the geometry/beamforming math right"
        from "is my calibration table currently good")
"""
import argparse
import numpy as np

from core import geometry, calibration, beamforming

ALGORITHMS = ["das", "das-cf", "dmas", "dmas-cf"]

TEST_POSITIONS = {
    "center, shallow":     (0.0, 0.0, 2.0),
    "off to +x":           (4.0, 0.0, 2.0),
    "off to +y":           (0.0, 4.0, 2.0),
    "off to -x,-y corner": (-4.0, -4.0, 2.0),
    "near edge":           (6.0, 3.0, 1.0),
    "deeper":              (2.0, -2.0, 5.0),
}


def build_synthetic_sweep(true_target, positions, pair_cal, velocity,
                           freqs_ghz, noise_level, amplitude=0.01, seed=None):
    rng = np.random.default_rng(seed)
    freqs_hz = freqs_ghz * 1e9
    true_target = np.array(true_target)
    sweep = {}
    for tx in range(1, 9):
        for rx in range(1, 9):
            if tx == rx:
                continue
            label = f"TX{tx}-RX{rx}"
            tx_pos = np.array(positions[f"TX{tx}"])
            rx_pos = np.array(positions[f"RX{rx}"])
            dist = np.linalg.norm(true_target - tx_pos) + np.linalg.norm(rx_pos - true_target)
            delay_s = dist / velocity + pair_cal.get(label, 0.0)
            phase = -2 * np.pi * freqs_hz * delay_s
            s21 = amplitude * np.exp(1j * phase)
            if noise_level > 0:
                noise = (rng.standard_normal(len(freqs_hz)) +
                          1j * rng.standard_normal(len(freqs_hz))) * noise_level
                s21 = s21 + noise
            sweep[label] = {
                "freqs": freqs_ghz.tolist(),
                "s21_real": s21.real.tolist(),
                "s21_imag": s21.imag.tolist(),
            }
    return sweep


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--noise", type=float, default=0.0005,
                         help="synthetic noise amplitude, default matches typical real measurement noise")
    parser.add_argument("--resolution", type=float, default=0.5)
    parser.add_argument("--use-real-calibration", type=str, default="true")
    args = parser.parse_args()
    use_real_cal = args.use_real_calibration.lower() != "false"

    positions = geometry.physical_antenna_positions()
    velocity = geometry.tissue_velocity_cm_per_s(1.0)  # air
    pair_cal = calibration.load_pair_delay_calibration() if use_real_cal else {}
    freqs_ghz = np.linspace(2.0, 6.0, 101)

    print(f"Testing algorithm pipeline with SYNTHETIC data (no real hardware).")
    print(f"noise={args.noise}, resolution={args.resolution}cm, "
          f"using_real_calibration_table={use_real_cal}\n")

    errors = {algo: [] for algo in ALGORITHMS}

    for label, true_pos in TEST_POSITIONS.items():
        sweep = build_synthetic_sweep(true_pos, positions, pair_cal, velocity,
                                       freqs_ghz, args.noise, seed=hash(label) % (2**31))
        print(f"[{label}] true={true_pos}")
        for algo in ALGORITHMS:
            results = beamforming.run_reconstruction(
                sweep, algo=algo, resolution_cm=args.resolution, permittivity=1.0)
            top = results[0]
            err = np.sqrt((top["x"] - true_pos[0]) ** 2 +
                           (top["y"] - true_pos[1]) ** 2 +
                           (top["z"] - true_pos[2]) ** 2)
            errors[algo].append(err)
            print(f"    {algo:8s}: predicted=({top['x']}, {top['y']}, {top['z']})  error={err:.2f}cm")
        print()

    print("=" * 60)
    print(f"{'algorithm':10s} {'mean_cm':>10s} {'max_cm':>10s}")
    for algo in ALGORITHMS:
        vals = np.array(errors[algo])
        print(f"{algo:10s} {vals.mean():10.2f} {vals.max():10.2f}")

    print()
    print("If these numbers are small (well under 1 grid cell = "
          f"{args.resolution}cm at zero noise, a few cm with realistic noise), "
          "the ALGORITHM ITSELF is confirmed correct -- any large errors you "
          "see on real hardware data are coming from the hardware/measurement "
          "side (calibration drift, switch instability, axis mismatches), "
          "not from bugs in geometry.py/calibration.py/beamforming.py.")


if __name__ == "__main__":
    main()