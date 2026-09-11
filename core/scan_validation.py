"""Validate physical-array spectra before accepting captures or imaging."""
import numpy as np
from .geometry import physical_antenna_positions


def validate_full_sweep(sweep):
    positions = physical_antenna_positions()
    expected = {f"{tx}-{rx}" for tx in positions if tx.startswith("TX")
                for rx in positions if rx.startswith("RX")}
    missing = sorted(expected - set(sweep))
    if missing:
        raise ValueError(f"Missing {len(missing)} of {len(expected)} pairs: {missing[:6]}")
    reference = None
    for label in sorted(expected):
        data = sweep[label]
        arrays = [np.asarray(data.get(k, []), dtype=float) for k in ("freqs", "s21_real", "s21_imag")]
        if any(a.ndim != 1 or len(a) != 101 or not np.all(np.isfinite(a)) for a in arrays):
            raise ValueError(f"{label}: expected 101 finite frequency, real and imaginary values")
        freqs = arrays[0]
        if not np.all(np.diff(freqs) > 0) or not np.allclose(np.diff(freqs), np.diff(freqs)[0], rtol=1e-6, atol=1e-10):
            raise ValueError(f"{label}: frequency grid must increase uniformly")
        if reference is None:
            reference = freqs
        elif not np.allclose(freqs, reference, rtol=1e-8, atol=1e-10):
            raise ValueError(f"{label}: frequency grid differs from other pairs")
        if not np.any(arrays[1] != 0) and not np.any(arrays[2] != 0):
            raise ValueError(f"{label}: zero-valued spectrum")
    return {"pairs": len(expected), "points": 101, "min_ghz": float(reference[0]), "max_ghz": float(reference[-1])}
