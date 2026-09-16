"""
beamforming.py -- tumor-localization reconstruction. Supports four
algorithms sharing the SAME validated pair-selection, per-pair delay
calibration, and near-field guard logic:

  "das"       -- plain delay-and-sum
  "das-cf"    -- DAS with coherence-factor weighting (the last validated
                 working version from the original das_imaging.py)
  "dmas"      -- delay-multiply-and-sum (pairwise sign-preserving
                 multiply-sum across pair contributions; better sidelobe
                 suppression than plain DAS, more compute -- O(pairs^2))
  "dmas-cf"   -- DMAS with the same coherence-factor weighting as das-cf

Use validate.py to measure which one actually performs best on YOUR
real, labeled scan data rather than assuming.
"""
from __future__ import annotations
from itertools import combinations
from typing import Optional

from . import geometry
from . import calibration
from . import timedomain

ASSUMED_PERMITTIVITY = 1.0  # tissue-phase placeholder; pass 1.0 for air


def _voxel_delays(voxels, positions, tx, rx, velocity, pair_delay_calibration, label):
    """Shared delay computation for a single pair, across all voxels."""
    import numpy as np
    tx_pos = np.array(positions[f"TX{tx}"])
    rx_pos = np.array(positions[f"RX{rx}"])
    dist_tx = np.linalg.norm(voxels - tx_pos, axis=1)
    dist_rx = np.linalg.norm(voxels - rx_pos, axis=1)
    pair_delay_s = pair_delay_calibration[label]
    delay_s = (dist_tx + dist_rx) / velocity + pair_delay_s
    return dist_tx, dist_rx, delay_s


def _gather_pair_contributions(sweep_plot_data, voxels, positions, velocity,
                                pair_delay_calibration, oversample, near_field_guard_cm,
                                min_freq_ghz=None, max_freq_ghz=None,
                                artifact_gate_ns=1.2):
    """Runs to_time_domain + delay interpolation for every usable pair.
    Returns (contributions: np.ndarray shape (P, V) complex, pairs_used: int,
    pair_labels: list[str]).

    min_freq_ghz/max_freq_ghz, if given, restrict EACH pair's spectrum to
    that band before windowing/IFFT -- e.g. single-band (non-UWB) antennas
    are only well-matched near resonance; frequencies far outside that
    band are dominated by impedance mismatch, not real coupled signal,
    and feeding them into the IFFT injects real artifacts into the
    time-domain response rather than just adding proportional noise.
    Confirmed empirically via capture_phase_stability.py's per-frequency
    breakdown: phase std >20-100deg below ~2.8GHz on this hardware,
    settling to <2deg from ~3.0GHz up -- the low band is noise, not
    signal, and was being reconstructed from anyway.

    artifact_gate_ns: maximum modeled PROPAGATION delay, excluding the
    per-pair system delay. Apply this support limit to interpolated voxel
    contributions, whose sample times still include system delay. An
    absolute 1.2 ns cutoff would erase legitimate samples with the current
    approximately 6-8 ns cable/switch delay calibration.
    This limit does not remove reflection sidelobes already overlapping
    the accepted time interval, nor validate the delay calibration. The
    default is intended for this air-filled dome; other media may need a
    longer interval or None to disable the limit."""
    import numpy as np

    contributions = []
    pair_labels = []
    for tx, rx, label, data in calibration.iter_usable_pairs(sweep_plot_data):
        freqs_hz = np.asarray(data["freqs"], dtype=float) * 1e9
        s21_complex = np.asarray(data["s21_real"]) + 1j * np.asarray(data["s21_imag"])

        if min_freq_ghz is not None or max_freq_ghz is not None:
            freqs_ghz = freqs_hz / 1e9
            lo = min_freq_ghz if min_freq_ghz is not None else freqs_ghz.min()
            hi = max_freq_ghz if max_freq_ghz is not None else freqs_ghz.max()
            band_mask = (freqs_ghz >= lo) & (freqs_ghz <= hi)
            if band_mask.sum() < 2:
                continue  # not enough points left in-band to IFFT this pair
            freqs_hz = freqs_hz[band_mask]
            s21_complex = s21_complex[band_mask]

        t, s_t = timedomain.to_time_domain(freqs_hz, s21_complex, oversample=oversample)

        dist_tx, dist_rx, delay_s = _voxel_delays(
            voxels, positions, tx, rx, velocity, pair_delay_calibration, label)

        re = np.interp(delay_s, t, s_t.real, left=0.0, right=0.0)
        im = np.interp(delay_s, t, s_t.imag, left=0.0, right=0.0)
        contribution = re + 1j * im

        if artifact_gate_ns is not None:
            propagation_s = (dist_tx + dist_rx) / velocity
            contribution[propagation_s > artifact_gate_ns * 1e-9] = 0.0

        too_close = (dist_tx < near_field_guard_cm) | (dist_rx < near_field_guard_cm)
        contribution[too_close] = 0.0

        contributions.append(contribution)
        pair_labels.append(label)

    if not contributions:
        return None, 0, []
    return np.array(contributions), len(contributions), pair_labels


def _coherence_factor(contributions, y_sum, pairs_used):
    import numpy as np
    sum_abs_sq = (np.abs(contributions) ** 2).sum(axis=0)
    raw_intensity = np.abs(y_sum) ** 2
    with np.errstate(divide="ignore", invalid="ignore"):
        cf = np.where(sum_abs_sq > 0, raw_intensity / (pairs_used * sum_abs_sq), 0.0)
    return np.clip(cf, 0.0, 1.0)


def _dmas_combine(contributions):
    """Pairwise sign-preserving multiply-sum across all pair combinations.
    O(pairs^2) but each step is vectorized over all voxels at once, so
    it's fast in practice for typical pair counts (~50-60) and voxel
    counts (a few thousand to ~10k for 0.5cm resolution)."""
    import numpy as np
    n_voxels = contributions.shape[1]
    s = np.zeros(n_voxels, dtype=float)
    for i, j in combinations(range(contributions.shape[0]), 2):
        prod = contributions[i] * np.conj(contributions[j])
        s += np.sign(prod.real) * np.sqrt(np.abs(prod))
    return s  # real-valued


def run_reconstruction(sweep_plot_data: dict, algo: str = "das-cf",
                        resolution_cm: float = 0.5, oversample: int = 8,
                        permittivity: float = ASSUMED_PERMITTIVITY,
                        near_field_guard_cm: float = 1.0, coherence_power: float = 2.0,
                        baseline_plot_data: Optional[dict] = None,
                        min_freq_ghz: Optional[float] = None,
                        max_freq_ghz: Optional[float] = None,
                        artifact_gate_ns: Optional[float] = 1.2,
                        pair_delay_calibration: Optional[dict] = None) -> list[dict]:
    """
    algo: "das", "das-cf", "dmas", or "dmas-cf"
    min_freq_ghz/max_freq_ghz: restrict reconstruction to this frequency
        band (see _gather_pair_contributions docstring) -- None (default)
        uses the full swept range, unchanged behavior.
    artifact_gate_ns: maximum propagation delay after excluding the
        per-pair system offset. Pass None to disable this support limit.
    pair_delay_calibration: explicit saved delay table for replaying a capture;
        None loads the current table. An empty table is never a fallback.
    Returns a list of {"x","y","z","intensity","coherence"} dicts sorted
    by intensity descending (index 0 = the candidate location). Returns
    [] if there is no finite, positive image signal. A nonempty image
    still requires a separate detection/confidence check.
    """
    import numpy as np

    algo = algo.lower()
    if algo not in ("das", "das-cf", "dmas", "dmas-cf"):
        raise ValueError(f"Unknown algo {algo!r}: must be das, das-cf, dmas, or dmas-cf")
    if artifact_gate_ns is not None and (not np.isfinite(artifact_gate_ns) or artifact_gate_ns <= 0):
        raise ValueError("artifact_gate_ns must be positive and finite, or None")

    if baseline_plot_data is not None:
        sweep_plot_data = calibration.subtract_baseline(sweep_plot_data, baseline_plot_data)

    if pair_delay_calibration is None:
        pair_delay_calibration = calibration.load_pair_delay_calibration()
    calibration.require_pair_delays(sweep_plot_data, pair_delay_calibration)

    positions = geometry.physical_antenna_positions()
    velocity = geometry.tissue_velocity_cm_per_s(permittivity)
    voxels = geometry.build_voxel_grid(resolution_cm=resolution_cm)

    contributions, pairs_used, _ = _gather_pair_contributions(
        sweep_plot_data, voxels, positions, velocity, pair_delay_calibration,
        oversample, near_field_guard_cm, min_freq_ghz=min_freq_ghz, max_freq_ghz=max_freq_ghz,
        artifact_gate_ns=artifact_gate_ns)

    if contributions is None:
        return []

    y_sum = contributions.sum(axis=0)

    if algo in ("das", "das-cf"):
        intensity = np.abs(y_sum) ** 2
        coherence = _coherence_factor(contributions, y_sum, pairs_used)
        if algo == "das-cf":
            intensity = intensity * (coherence ** coherence_power)
    else:  # dmas, dmas-cf
        dmas_signal = _dmas_combine(contributions)
        intensity = np.abs(dmas_signal)
        coherence = _coherence_factor(contributions, y_sum, pairs_used)
        if algo == "dmas-cf":
            intensity = intensity * (coherence ** coherence_power)

    if not np.all(np.isfinite(intensity)) or not np.any(intensity > 0):
        return []

    order = np.argsort(-intensity)
    results = [
        {"x": round(float(voxels[i, 0]), 2), "y": round(float(voxels[i, 1]), 2),
         "z": round(float(voxels[i, 2]), 2), "intensity": float(intensity[i]),
         "coherence": round(float(coherence[i]), 3)}
        for i in order
    ]
    return results


def snr_check(results: list[dict], min_ratio: float = 6.0, min_coherence: float = 0.15) -> dict:
    """Requires BOTH a strong peak-to-mean ratio AND real coherence --
    ratio alone can be fooled by noise after baseline subtraction.

    min_coherence lowered from 0.3 -> 0.15 based on real hardware data:
    empty-dome coherence ranged ~0.08-0.14, real-target coherence ranged
    ~0.09-0.21 across captured test scans -- the two ranges OVERLAP, so no
    threshold here cleanly separates them. 0.15 clears most careful
    same-position real-target repeats while still rejecting most empty-
    dome readings, but it's a best-available compromise, not a clean
    discriminator. Revisit once validate.py has enough labeled scans to
    give a real false-positive/false-negative rate at this threshold --
    the deeper fix is likely improving coherence itself (phase/pair-delay
    calibration, more averaging), not just moving this line."""
    import numpy as np
    if not results:
        return {"confident": False, "peak_to_mean_ratio": 0.0, "coherence": 0.0}
    intensities = np.array([r["intensity"] for r in results])
    peak = intensities[0]
    peak_coherence = results[0].get("coherence", 0.0)
    if not np.all(np.isfinite(intensities)) or peak <= 0 or not np.isfinite(peak_coherence):
        return {"confident": False, "peak_to_mean_ratio": 0.0, "coherence": 0.0}
    mean_rest = intensities[1:].mean() if len(intensities) > 1 else 0.0
    ratio = float(peak / mean_rest) if mean_rest > 0 else float("inf")
    confident = (ratio >= min_ratio) and (peak_coherence >= min_coherence)
    return {"confident": confident, "peak_to_mean_ratio": round(ratio, 2), "coherence": peak_coherence}


def estimate_tumor_extent(results: list[dict], threshold_fraction: float = 0.5,
                           resolution_cm: float = 0.5) -> Optional[dict]:
    """
    Estimate the spatial extent of the localized target from a
    run_reconstruction() result list -- "how big/spread-out is the hot
    region", complementing the single-voxel results[0] location.

    Selects every voxel with intensity >= threshold_fraction * peak
    intensity (results[0]'s intensity, since results is sorted descending).
    Returns None if results is empty or the peak intensity is <= 0.

    Returns a dict:
      - voxel_count: how many voxels cleared the threshold
      - centroid: {"x","y","z"} intensity-weighted center of the cluster (cm)
      - bounding_box: {"x_min","x_max","y_min","y_max","z_min","z_max"} (cm)
      - extent_cm: {"x","y","z"} bounding-box side lengths (cm)
      - max_diameter_cm: largest pairwise distance between any two
        thresholded voxels -- an upper bound on target size, only
        meaningful for a single compact hot region (multiple separate
        hot spots will inflate this)
      - volume_cm3: voxel_count * resolution_cm**3 -- a rough proxy from
        counting grid cubes, not a true segmented volume
    """
    import numpy as np

    if not results:
        return None
    peak_intensity = results[0]["intensity"]
    if peak_intensity <= 0:
        return None
    threshold = peak_intensity * threshold_fraction

    selected = [r for r in results if r["intensity"] >= threshold]
    if not selected:
        selected = [results[0]]

    pts = np.array([[r["x"], r["y"], r["z"]] for r in selected])
    weights = np.array([r["intensity"] for r in selected])
    centroid = (pts * weights[:, None]).sum(axis=0) / weights.sum()
    x_min, y_min, z_min = pts.min(axis=0)
    x_max, y_max, z_max = pts.max(axis=0)

    if len(pts) > 1:
        diffs = pts[:, None, :] - pts[None, :, :]
        max_diameter_cm = float(np.sqrt((diffs ** 2).sum(axis=-1)).max())
    else:
        max_diameter_cm = 0.0

    return {
        "voxel_count": len(selected),
        "centroid": {"x": round(float(centroid[0]), 2), "y": round(float(centroid[1]), 2),
                     "z": round(float(centroid[2]), 2)},
        "bounding_box": {"x_min": round(float(x_min), 2), "x_max": round(float(x_max), 2),
                          "y_min": round(float(y_min), 2), "y_max": round(float(y_max), 2),
                          "z_min": round(float(z_min), 2), "z_max": round(float(z_max), 2)},
        "extent_cm": {"x": round(float(x_max - x_min), 2), "y": round(float(y_max - y_min), 2),
                      "z": round(float(z_max - z_min), 2)},
        "max_diameter_cm": round(max_diameter_cm, 2),
        "volume_cm3": round(len(selected) * (resolution_cm ** 3), 3),
    }
