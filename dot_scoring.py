"""
dot_scoring.py -- ported directly from the FastAPI app's main.py
(simulate_side_from_real_data() and its helpers), so it can run standalone
from this repo without importing from naibra_project.

Turns per-TX-RX-pair signal weights (from
scan_engine.compute_sensor_weights_from_traces()) into the dot-cloud /
severity-out-of-100 score used by the GUI's dome visualization.
"""
import json
import math
import os
from typing import Dict, List, Optional
BASELINE_SENSITIVITY_DB = 6.0

# ---------------------------------------------------------------------------
# DAS absolute-severity calibration
# ---------------------------------------------------------------------------
# das_to_dome_result() used to compute severity as
#     intensity / this_scan's_own_peak_intensity
# which made the peak voxel ALWAYS severity 1.0, no matter how strong or
# weak the real underlying signal actually was -- an empty dome and a real
# target could end up producing nearly the same score, because everything
# was normalized against itself instead of against anything absolute.
#
# Fixed by comparing each scan's peak intensity against two FIXED reference
# points instead:
#   floor_intensity   -- peak DAS/DMAS-CF intensity with nothing in the
#                         dome (pure measurement noise, no real target).
#   ceiling_intensity -- peak DAS/DMAS-CF intensity for a known, real
#                         target (e.g. a metal reflector or a hand).
# severity = clamp((intensity - floor) / (ceiling - floor), 0, 1)
#
# PLACEHOLDER VALUES BELOW -- not yet measured from real hardware. Once you
# run an empty-dome scan and a known-target scan, note their das_top_location
# / dmas_top_location "intensity" values from the /api/scan/start response
# and either edit the two constants below, or (preferred, no code change
# needed) create data/das_severity_calibration.json:
#   {"floor_intensity": <empty-dome peak>, "ceiling_intensity": <known-target peak>}
DATA_DIR = "data"
DAS_SEVERITY_CALIBRATION_FILE = os.path.join(DATA_DIR, "das_severity_calibration.json")
DAS_FLOOR_INTENSITY_DEFAULT = 1.0
DAS_CEILING_INTENSITY_DEFAULT = 10.0  # arbitrary placeholder until real target data exists


def load_das_severity_calibration() -> Dict[str, float]:
    """{"floor_intensity": ..., "ceiling_intensity": ...}. Missing/unreadable
    file -> the placeholder defaults above (see module docstring)."""
    if os.path.exists(DAS_SEVERITY_CALIBRATION_FILE):
        try:
            with open(DAS_SEVERITY_CALIBRATION_FILE) as f:
                cal = json.load(f)
            return {
                "floor_intensity": float(cal.get("floor_intensity", DAS_FLOOR_INTENSITY_DEFAULT)),
                "ceiling_intensity": float(cal.get("ceiling_intensity", DAS_CEILING_INTENSITY_DEFAULT)),
            }
        except Exception:
            pass
    return {
        "floor_intensity": DAS_FLOOR_INTENSITY_DEFAULT,
        "ceiling_intensity": DAS_CEILING_INTENSITY_DEFAULT,
    }


def compute_weights_from_baseline(raw_s21_db: Dict[str, float], baseline_raw: Dict[str, float],
                                   sensitivity_db: float = BASELINE_SENSITIVITY_DB) -> Dict[str, float]:
    """
    Turn this scan's raw per-pair dB averages into 0..1 weights by
    comparing against the empty-device baseline, instead of min-max
    normalizing within this scan's own values (which always makes SOME
    pair look "high" even with nothing in the device -- that's why an
    empty-dome scan was scoring 51/100 instead of ~99).

        weight = clamp(|current_dB - baseline_dB| / sensitivity_db, 0, 1)

    A pair identical to its baseline scores 0 (no anomaly-signal). A pair
    sensitivity_db or more away from baseline scores 1 (maximal).
    """
    weights: Dict[str, float] = {}
    for label, cur_db in raw_s21_db.items():
        base_db = baseline_raw.get(label)
        if base_db is None:
            weights[label] = 0.0
            continue
        delta_db = abs(cur_db - base_db)
        weights[label] = max(0.0, min(1.0, delta_db / sensitivity_db))
    return weights


def _seg_seg_closest(p1, p2, p3, p4):
    """Closest distance + midpoint between two 3D segments."""
    d1 = (p2[0] - p1[0], p2[1] - p1[1], p2[2] - p1[2])
    d2 = (p4[0] - p3[0], p4[1] - p3[1], p4[2] - p3[2])
    r = (p1[0] - p3[0], p1[1] - p3[1], p1[2] - p3[2])
    a = sum(d1[i] * d1[i] for i in range(3))
    e = sum(d2[i] * d2[i] for i in range(3))
    f = sum(d2[i] * r[i] for i in range(3))
    b = sum(d1[i] * d2[i] for i in range(3))
    c = sum(d1[i] * r[i] for i in range(3))
    denom = a * e - b * b
    s = max(0.0, min(1.0, (b * f - c * e) / denom)) if denom > 1e-9 else 0.0
    t = (b * s + f) / e if e > 1e-9 else 0.0
    t = max(0.0, min(1.0, t))
    c1 = (p1[0] + d1[0] * s, p1[1] + d1[1] * s, p1[2] + d1[2] * s)
    c2 = (p3[0] + d2[0] * t, p3[1] + d2[1] * t, p3[2] + d2[2] * t)
    mid = ((c1[0] + c2[0]) / 2, (c1[1] + c2[1]) / 2, (c1[2] + c2[2]) / 2)
    return math.dist(c1, c2), mid


def _cat(sev: float) -> str:
    if sev >= 0.70:
        return "high"
    if sev >= 0.50:
        return "medium"
    if sev >= 0.32:
        return "low"
    return "baseline"


REGION_LABELS = ["Right", "Top-Right", "Top", "Top-Left", "Left", "Bottom-Left", "Bottom", "Bottom-Right"]
REGION_CENTER_RADIUS = 0.12


def region_label(x: float, y: float) -> str:
    if (x * x + y * y) ** 0.5 < REGION_CENTER_RADIUS:
        return "Center"
    angle = math.degrees(math.atan2(y, x)) % 360
    idx = int(((angle + 22.5) % 360) // 45)
    return REGION_LABELS[idx]


def region_breakdown(dots: List[dict]) -> Dict[str, Dict[str, int]]:
    out = {r: {"high": 0, "medium": 0, "low": 0, "baseline": 0} for r in REGION_LABELS + ["Center"]}
    for d in dots:
        out[d["region"]][d["c"]] += 1
    return out


def ring_antenna_positions(num_antennas: int = 12, ring_polar_deg: float = 62.0) -> List[dict]:
    out = []
    polar = math.radians(ring_polar_deg)
    for i in range(num_antennas):
        theta = 2 * math.pi * i / num_antennas
        out.append({
            "x": round(math.sin(polar) * math.cos(theta), 4),
            "y": round(math.sin(polar) * math.sin(theta), 4),
            "z": round(math.cos(polar), 4),
        })
    return out


def simulate_side_from_real_data(weights: Dict[str, float], num_antennas: int = 12) -> dict:
    """
    Real-data dot-cloud + severity score. Uses actual per-TX-RX-pair
    weights from scan_engine.compute_sensor_weights_from_traces() (real
    S21 measurements) instead of simulated anomalies.
    """
    ring = ring_antenna_positions(num_antennas)
    pts = [(a["x"], a["y"], a["z"]) for a in ring]

    lines = []
    for i in range(num_antennas):
        for j in range(i + 1, num_antennas):
            fwd = weights.get(f"TX{i + 1}-RX{j + 1}")
            rev = weights.get(f"TX{j + 1}-RX{i + 1}")
            vals = [v for v in (fwd, rev) if v is not None]
            if not vals:
                continue
            lines.append((i, j, sum(vals) / len(vals)))

    empty_breakdown = region_breakdown([])
    if not lines:
        return {
            "dots": [], "score": 0, "mean_severity": 0, "max_severity": 0, "anomaly_count": 0,
            "dot_counts": {"high": 0, "medium": 0, "low": 0, "baseline": 0},
            "region_counts": empty_breakdown, "worst_region": None,
        }

    lines.sort(key=lambda ln: -ln[2])
    top = lines

    STRONG_LINE_WEIGHT = 0.5

    dots = []
    lines_with_a_dot = set()
    for a_i in range(len(top)):
        for b_i in range(a_i + 1, len(top)):
            i1, j1, v1 = top[a_i]
            i2, j2, v2 = top[b_i]
            if len({i1, j1, i2, j2}) < 4:
                continue
            gap, mid = _seg_seg_closest(pts[i1], pts[j1], pts[i2], pts[j2])
            if gap > 0.065:
                continue
            r2 = mid[0] ** 2 + mid[1] ** 2 + mid[2] ** 2
            if r2 > 0.92 or mid[2] < 0.04:
                continue
            sev = max(0.0, min(1.0, max(v1, v2)))
            dots.append({
                "x": round(mid[0], 3), "y": round(mid[1], 3), "z": round(mid[2], 3),
                "s": round(sev, 3), "c": _cat(sev), "region": region_label(mid[0], mid[1]),
            })
            lines_with_a_dot.add(a_i)
            lines_with_a_dot.add(b_i)

    for idx, (i1, j1, v1) in enumerate(top):
        if v1 < STRONG_LINE_WEIGHT or idx in lines_with_a_dot:
            continue
        mid = tuple((pts[i1][k] + pts[j1][k]) / 2 for k in range(3))
        r2 = mid[0] ** 2 + mid[1] ** 2 + mid[2] ** 2
        if r2 > 0.92 or mid[2] < 0.04:
            continue
        sev = max(0.0, min(1.0, v1))
        dots.append({
            "x": round(mid[0], 3), "y": round(mid[1], 3), "z": round(mid[2], 3),
            "s": round(sev, 3), "c": _cat(sev), "region": region_label(mid[0], mid[1]),
        })

    dots.sort(key=lambda d: -d["s"])

    max_sev = max((d["s"] for d in dots), default=0.2)
    mean_sev = sum(d["s"] for d in dots) / len(dots) if dots else 0.2
    high_count = sum(1 for d in dots if d["c"] == "high")
    penalty = 0.0
    if max_sev > 0.45:
        penalty += (max_sev - 0.45) * 95
    penalty += min(18.0, high_count * 0.6)
    score = int(round(max(22, min(99, 100 - penalty))))
    r_breakdown = region_breakdown(dots)
    worst_region = max(
        r_breakdown.items(),
        key=lambda kv: (kv[1]["high"] * 3 + kv[1]["medium"]),
        default=(None, None),
    )[0]
    if worst_region and (r_breakdown[worst_region]["high"] + r_breakdown[worst_region]["medium"]) == 0:
        worst_region = None
    return {
        "dots": dots,
        "score": score,
        "mean_severity": round(mean_sev, 3),
        "max_severity": round(max_sev, 3),
        "anomaly_count": 0,
        "dot_counts": {
            "high": high_count,
            "medium": sum(1 for d in dots if d["c"] == "medium"),
            "low": sum(1 for d in dots if d["c"] == "low"),
            "baseline": sum(1 for d in dots if d["c"] == "baseline"),
        },
        "region_counts": r_breakdown,
        "worst_region": worst_region,
    }


def das_to_dome_result(das_results: List[dict], confident: bool,
                        dome_radius_cm: float = 8.0,
                        threshold_fraction: float = 0.5,
                        floor_intensity: Optional[float] = None,
                        ceiling_intensity: Optional[float] = None) -> dict:
    """Compatibility entrypoint: DMAS-CF locations only; no severity calibration."""
    from dmas_localization import localization_result
    return localization_result(das_results, confident, dome_radius_cm, threshold_fraction)
