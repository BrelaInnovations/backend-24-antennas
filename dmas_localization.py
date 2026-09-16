"""Convert DMAS-CF voxels to a relative-intensity 3D thermal dot cloud."""
import math

from core.geometry import DOME_RADIUS_CM, physical_antenna_positions


def localization_antennas():
    """Use the same geometry and coordinate scale as the reconstruction."""
    return [{"id": name, "label": name, "enabled": True,
             "prong": (0 if name.startswith("TX") else 3) + (int(name[2:]) - 1) // 4,
             "x": xyz[0] / DOME_RADIUS_CM, "y": xyz[1] / DOME_RADIUS_CM,
             "z": xyz[2] / DOME_RADIUS_CM}
            for name, xyz in physical_antenna_positions().items()]


def localization_result(voxels, confident, dome_radius_cm=DOME_RADIUS_CM,
                        threshold_fraction=0.05, max_dots=4096):
    """Preserve voxel coordinates; threshold selects the displayed field only.

    Colours and size use intensity relative to this scan's peak.
    Raw intensity is retained; these display bands are not clinical severity.
    A bounded, deterministic sample covers the selected field on mobile devices.
    Confidence describes reconstruction quality, not a health assessment.
    """
    if not math.isfinite(dome_radius_cm) or dome_radius_cm <= 0:
        raise ValueError("dome_radius_cm must be positive and finite")
    if not 0 < threshold_fraction <= 1:
        raise ValueError("threshold_fraction must be in (0, 1]")
    if not isinstance(max_dots, int) or max_dots < 1:
        raise ValueError("max_dots must be a positive integer")
    valid = []
    for voxel in voxels or []:
        try:
            point = {k: float(voxel[k]) for k in ("x", "y", "z", "intensity")}
        except (KeyError, TypeError, ValueError, OverflowError):
            continue
        if all(math.isfinite(v) for v in point.values()) and point["intensity"] > 0:
            valid.append(point)
    valid.sort(key=lambda v: (-v["intensity"], v["x"], v["y"], v["z"]))
    peak = valid[0] if valid else None
    selected = [v for v in valid if v["intensity"] >= peak["intensity"] * threshold_fraction] if peak else []
    selected_count = len(selected)
    if selected_count > max_dots:
        selected = [selected[i * selected_count // max_dots] for i in range(max_dots)]
    def intensity_band(relative):
        if relative >= 0.75:
            return "high"
        if relative >= 0.45:
            return "medium"
        if relative >= 0.20:
            return "low"
        return "baseline"

    dots = [{"x": v["x"] / dome_radius_cm,
             "y": v["y"] / dome_radius_cm,
             "z": v["z"] / dome_radius_cm,
             "intensity": v["intensity"], "source": "dmas-cf",
             "relative_intensity": v["intensity"] / peak["intensity"],
             # Existing dome renderer uses c for colour and s for dot size.
             "s": v["intensity"] / peak["intensity"],
             "c": intensity_band(v["intensity"] / peak["intensity"])} for v in selected]
    status = "localized" if dots and confident else "inconclusive" if valid else "unavailable"
    return {
        "source": "dmas-cf", "display_mode": "localization", "status": status,
        "color_mode": "relative_intensity",
        "display_notice": ("Inconclusive reconstruction — showing the measured field for inspection, not a confirmed location."
                           if valid and not confident else None),
        "intensity_scale": {"reference": "scan_peak", "red_min": 0.75, "orange_min": 0.45,
                            "green_min": 0.20, "blue_min": threshold_fraction},
        "dots": dots, "dot_count": len(dots), "selected_voxel_count": selected_count,
        "sampled": selected_count > len(dots), "peak_location_cm": peak if confident else None,
        "candidate_peak_location_cm": peak,
        "coordinate_system": {"units": "normalized", "radius_cm": dome_radius_cm,
                              "axes": "+Y toward RX5-8; +X 90 degrees clockwise viewed from above; +Z above base"},
        "threshold_fraction": threshold_fraction, "confident": bool(confident and peak),
        # Nullable compatibility fields for existing list clients. No fabricated scores.
        "score": None, "mean_severity": None, "max_severity": None,
        "anomaly_count": None,
        "dot_counts": {band: sum(d["c"] == band for d in dots) for band in ("high", "medium", "low", "baseline")},
        "region_counts": {}, "worst_region": None,
    }


def localization_metrics(left, right):
    localized = left.get("status") == "localized" or right.get("status") == "localized"
    return {
        "display_mode": "localization", "overall_score": None,
        "verdict": "localized" if localized else "inconclusive",
        "verdict_label": "DMAS-CF locations" if localized else "Localization inconclusive",
        "left_right": {"left": None, "right": None, "asymmetry": None},
        "standard_vs_current": None, "past_vs_current": None, "alert": None,
        "recommendations": ["Dot colours show relative DMAS-CF intensity, not tissue safety. Both views share one physical capture."],
    }
