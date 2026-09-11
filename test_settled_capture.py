"""Hardware-free tests for full-scan settling metrics."""
import copy
import unittest

from capture_settled_labeled_scan import similarity


def scan(value=1 + 0j):
    return {
        f"TX{tx}-RX{rx}": {
            "freqs": [2 + 0.04 * i for i in range(101)],
            "s21_real": [value.real] * 101,
            "s21_imag": [value.imag] * 101,
        }
        for tx in range(1, 9) for rx in range(1, 9)
    }


class SettledCaptureTests(unittest.TestCase):
    def test_identical_scans_settle(self):
        result = similarity(scan(), scan())
        self.assertTrue(result["settled"])
        self.assertEqual(result["complex_correlation"], 1.0)
        self.assertEqual(result["relative_rms_difference"], 0.0)

    def test_phase_shift_is_rejected(self):
        result = similarity(scan(), scan(0 + 1j))
        self.assertFalse(result["settled"])

    def test_incomplete_pair_is_rejected(self):
        incomplete = scan()
        del incomplete["TX1-RX1"]
        with self.assertRaises(ValueError):
            similarity(scan(), incomplete)


if __name__ == "__main__":
    unittest.main()
