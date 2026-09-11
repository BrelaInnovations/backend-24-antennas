"""Preserve reference files and geometry with each new capture."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from .geometry import DOME_RADIUS_CM, physical_antenna_positions


def save_provenance(scan_path, kind, extra=None):
    root = Path(__file__).resolve().parents[1]
    scan_path = Path(scan_path).resolve()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    folder = root / "data" / "capture_sessions" / stamp
    folder.mkdir(parents=True)
    files = {}
    for path in [scan_path, root / "data/baseline_full_sweep.json",
                 root / "data/pair_delay_calibration.json", root / "data/switch_role_config.json",
                 root / "data/phase_stability_results.json", root / "2-6_cal_with_new_cable.cal"]:
        if path.exists():
            raw = path.read_bytes()
            (folder / path.name).write_bytes(raw)
            files[str(path.relative_to(root))] = {"sha256": hashlib.sha256(raw).hexdigest(), "snapshot": path.name}
    metadata = {"captured_at_utc": stamp, "kind": kind, "radius_cm": DOME_RADIUS_CM,
                "axes": "+Y RX5-8; +X 90 degrees clockwise viewed from above; +Z above base", "positions_cm": physical_antenna_positions(),
                "files": files, "details": extra or {}}
    (folder / "metadata.json").write_text(json.dumps(metadata, indent=2))
    scan_path.with_suffix(".provenance.json").write_text(json.dumps({"session": str(folder.relative_to(root))}, indent=2))
    return folder
