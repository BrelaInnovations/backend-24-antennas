"""timedomain.py -- frequency-domain S21 sweep -> time-domain response."""
from __future__ import annotations


def to_time_domain(freqs_hz, s21_complex, oversample: int = 8):
    """
    Convert one antenna-pair's frequency-domain S21 sweep into a
    time-domain response s(t) via a windowed, zero-padded IFFT.
    Returns (t_seconds: np.ndarray, s_t: np.ndarray of complex)
    """
    import numpy as np

    freqs_hz = np.asarray(freqs_hz, dtype=float)
    s21 = np.asarray(s21_complex, dtype=complex)
    n = len(freqs_hz)
    if n < 2:
        raise ValueError("Need at least 2 frequency points to IFFT")

    window = np.hanning(n)
    s21 = s21 * window

    df = freqs_hz[1] - freqs_hz[0]
    f_start = freqs_hz[0]
    f_stop = freqs_hz[-1]

    n_bins_to_stop = int(round(f_stop / df)) + 1
    n_bins_to_start = int(round(f_start / df))

    total_bins = n_bins_to_stop * oversample
    spectrum = np.zeros(total_bins, dtype=complex)
    spectrum[n_bins_to_start:n_bins_to_start + n] = s21

    s_t = np.fft.ifft(spectrum)
    dt = 1.0 / (total_bins * df)
    t = np.arange(total_bins) * dt
    return t, s_t
