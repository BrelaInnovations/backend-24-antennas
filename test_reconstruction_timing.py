"""Offline regression tests for calibrated timing and invalid images."""
import unittest
from unittest.mock import patch
import numpy as np
from core import beamforming, geometry


class ReconstructionTimingTests(unittest.TestCase):
    def setUp(self):
        self.target = np.array([2., 2., 3.])
        self.freq = np.linspace(2e9, 6e9, 101)
        self.delays = {}
        self.scan = {}
        positions = geometry.physical_antenna_positions()
        for tx in range(1, 9):
            for rx in range(1, 9):
                label = f'TX{tx}-RX{rx}'
                offset = (6 + 0.05*tx + 0.08*rx)*1e-9
                self.delays[label] = offset
                path = np.linalg.norm(self.target-positions[f'TX{tx}']) + np.linalg.norm(self.target-positions[f'RX{rx}'])
                signal = np.exp(-2j*np.pi*self.freq*(offset+path/geometry.SPEED_OF_LIGHT_CM_PER_S))
                self.scan[label] = {'freqs': (self.freq/1e9).tolist(), 's21_real': signal.real.tolist(), 's21_imag': signal.imag.tolist()}

    def reconstruct(self, **kwargs):
        with patch('core.calibration.load_pair_delay_calibration', return_value=self.delays):
            return beamforming.run_reconstruction(self.scan, **kwargs)

    def test_known_target_survives_system_delay_for_all_algorithms(self):
        for algo in ['das', 'das-cf', 'dmas', 'dmas-cf']:
            with self.subTest(algo=algo):
                result = self.reconstruct(algo=algo)
                self.assertTrue(result)
                predicted = [result[0][k] for k in ('x','y','z')]
                self.assertLessEqual(np.linalg.norm(predicted-self.target), 0.5)

    def test_gate_preserves_in_dome_samples(self):
        gated = self.reconstruct()
        ungated = self.reconstruct(artifact_gate_ns=None)
        self.assertEqual(gated, ungated)

    def test_too_short_gate_rejects_paths(self):
        self.assertEqual(self.reconstruct(artifact_gate_ns=0.001), [])

    def test_identical_baseline_has_no_candidate(self):
        for algo in ['das', 'das-cf', 'dmas', 'dmas-cf']:
            with self.subTest(algo=algo):
                self.assertEqual(self.reconstruct(algo=algo, baseline_plot_data=self.scan), [])

    def test_zero_or_nonfinite_image_not_confident(self):
        for intensity in [0., float('nan'), float('inf')]:
            result = beamforming.snr_check([{'intensity': intensity, 'coherence': 1.}])
            self.assertFalse(result['confident'])
            self.assertEqual(result['peak_to_mean_ratio'], 0.)

    def test_invalid_gate_rejected(self):
        for gate in [0., -1., float('nan'), float('inf')]:
            with self.assertRaises(ValueError):
                self.reconstruct(artifact_gate_ns=gate)


if __name__ == '__main__':
    unittest.main()
