"""Load and verify references belonging to a saved target capture."""
import hashlib
import json
from pathlib import Path
import numpy as np
from . import geometry, calibration


def load_reference_snapshot(scan_path):
    """Return saved baseline/delays, or None for a legacy scan without a sidecar.

    A broken or mismatched sidecar is an error, never a silent fallback to
    current references. Geometry must match so antenna overlays and imaging
    cannot disagree. Baseline snapshots themselves are not target captures.
    """
    path = Path(scan_path).resolve()
    sidecar = path.with_suffix(".provenance.json")
    if not sidecar.exists():
        return None
    root = Path(__file__).resolve().parents[1]
    session = (root / json.loads(sidecar.read_text())["session"].replace("\\", "/")).resolve()
    session.relative_to(root / "data" / "capture_sessions")
    meta = json.loads((session / "metadata.json").read_text())
    if meta.get("kind") != "target":
        return None
    entries = {k.replace("\\", "/"): v for k, v in meta["files"].items()}

    def read_verified(key):
        item = entries[key]
        source = (session / item["snapshot"]).resolve()
        source.relative_to(session)
        raw = source.read_bytes()
        if hashlib.sha256(raw).hexdigest() != item["sha256"]:
            raise ValueError(f"Changed snapshot: {key}")
        return json.loads(raw)

    key = path.relative_to(root).as_posix()
    if hashlib.sha256(path.read_bytes()).hexdigest() != entries[key]["sha256"]:
        raise ValueError("Scan does not match its reference snapshot; use the original saved scan")
    positions = geometry.physical_antenna_positions()
    recorded = meta["positions_cm"]
    if meta["radius_cm"] != geometry.DOME_RADIUS_CM or set(recorded) != set(positions) or any(
        not np.allclose(recorded[k], positions[k], rtol=0, atol=1e-4) for k in positions
    ):
        raise ValueError("Recorded geometry differs from current geometry; do not silently reinterpret this scan")
    # Exclusion assets affect pair selection too. Refuse a different current
    # list rather than replaying with an unnoticed channel-selection change.
    if calibration.EXCLUDE_UNSTABLE_PHASE_PAIRS:
        key_phase = "data/phase_stability_results.json"
        if key_phase in entries:
            current = Path(calibration.PHASE_STABILITY_RESULTS_FILE)
            if not current.exists() or hashlib.sha256(current.read_bytes()).hexdigest() != entries[key_phase]["sha256"]:
                raise ValueError("Phase exclusion file differs from the capture snapshot")
    if calibration.EXCLUDE_WEAK_BASELINE_PAIRS:
        raise ValueError("Weak-pair exclusion was not snapshotted; cannot replay it reproducibly")
    return {"baseline": read_verified("data/baseline_full_sweep.json"),
            "delays": read_verified("data/pair_delay_calibration.json"),
            "session": str(session), "source_files": entries,
            "true_position_cm": meta.get("details", {}).get("true_position_cm")}
