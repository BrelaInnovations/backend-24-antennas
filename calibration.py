"""
calibration.py -- loads and applies a NanoVNA-Saver-format 2-port
calibration file (.cal) to raw S21 measurements.

The legacy Tkinter GUI required this .cal file to be manually loaded into
NanoVNA-Saver before a sweep, so its S21 readings were already corrected.
Our headless run_full_sweep()/scan_engine.py pipeline talks to the VNA
registers directly and had NO equivalent correction step -- this module
adds it back.

We only apply the S21 (transmission) correction, since scan_engine.py only
ever computes S21 (thru/fwd). The file also carries Short/Open/Load/
Thru-reflect terms for full 12-term correction (mainly useful for S11 /
port-match accuracy), but nothing in this codebase uses S11 today, so
those columns are parsed but unused for now.
"""

from __future__ import annotations

import bisect
import logging
from typing import Optional

logger = logging.getLogger("naibra.calibration")


class Calibration:
    def __init__(self, freqs_hz: list[int], through: list[complex], isolation: list[complex]):
        self.freqs_hz = freqs_hz  # must be sorted ascending
        self.through = through
        self.isolation = isolation

    @classmethod
    def load(cls, path: str) -> "Calibration":
        """
        Parse a NanoVNA-Saver .cal file:
            # Hz ShortR ShortI OpenR OpenI LoadR LoadI ThroughR ThroughI ThrureflR ThrureflI IsolationR IsolationI
        Lines starting with '#' (comments/header) are skipped.
        """
        freqs: list[int] = []
        through: list[complex] = []
        isolation: list[complex] = []

        with open(path, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split()
                if len(parts) < 13:
                    continue
                freq_hz = int(float(parts[0]))
                through_r, through_i = float(parts[7]), float(parts[8])
                iso_r, iso_i = float(parts[11]), float(parts[12])
                freqs.append(freq_hz)
                through.append(complex(through_r, through_i))
                isolation.append(complex(iso_r, iso_i))

        if not freqs:
            raise ValueError(f"No calibration points parsed from {path}")

        # Sort by frequency just in case the file isn't already ordered.
        order = sorted(range(len(freqs)), key=lambda i: freqs[i])
        freqs = [freqs[i] for i in order]
        through = [through[i] for i in order]
        isolation = [isolation[i] for i in order]
        return cls(freqs, through, isolation)

    def _interp_at(self, series: list[complex], freq_hz: float) -> complex:
        """Linear interpolation (real & imag independently) at an arbitrary
        frequency, clamped to the calibration file's own frequency range."""
        freqs = self.freqs_hz
        if freq_hz <= freqs[0]:
            return series[0]
        if freq_hz >= freqs[-1]:
            return series[-1]
        idx = bisect.bisect_right(freqs, freq_hz) - 1
        f0, f1 = freqs[idx], freqs[idx + 1]
        v0, v1 = series[idx], series[idx + 1]
        t = (freq_hz - f0) / (f1 - f0) if f1 != f0 else 0.0
        return complex(
            v0.real + (v1.real - v0.real) * t,
            v0.imag + (v1.imag - v0.imag) * t,
        )

    def correct_s21(self, freq_hz: float, s21_raw: complex) -> complex:
        """
        Standard thru + isolation correction:
            S21_corrected = (S21_raw - Isolation) / (Through - Isolation)

        Isolation removes the system's own leakage/crosstalk; dividing by
        (Through - Isolation) normalizes the system's transmission tracking
        so an ideal thru connection reads exactly 1 (0 dB, 0 deg) at every
        frequency. This is the same correction NanoVNA-Saver applies when
        this .cal file is loaded there.
        """
        iso = self._interp_at(self.isolation, freq_hz)
        thru = self._interp_at(self.through, freq_hz)
        denom = thru - iso
        if abs(denom) < 1e-12:
            logger.warning("Calibration denom ~0 at %.0f Hz, using raw S21", freq_hz)
            return s21_raw
        return (s21_raw - iso) / denom


_cache: dict[str, Calibration] = {}


def get_calibration(path: str) -> Calibration:
    """Load once per path and cache -- calibration files don't change
    between scans, no need to re-parse the file every sweep."""
    if path not in _cache:
        _cache[path] = Calibration.load(path)
    return _cache[path]