from pathlib import Path

p = Path('dot_scoring.py')
s = p.read_text(encoding='utf-8')
start = s.index('def das_to_dome_result(')
s = s[:start] + '''def das_to_dome_result(das_results: List[dict], confident: bool,
                        dome_radius_cm: float = 8.0,
                        threshold_fraction: float = 0.5,
                        floor_intensity: Optional[float] = None,
                        ceiling_intensity: Optional[float] = None) -> dict:
    """Compatibility entrypoint: DMAS-CF locations only; no severity calibration."""
    from dmas_localization import localization_result
    return localization_result(das_results, confident, dome_radius_cm, threshold_fraction)
'''
p.write_text(s, encoding='utf-8')

p = Path('server.py')
s = p.read_text(encoding='utf-8')
s = s.replace('import dot_scoring\n', 'import dot_scoring\nfrom dmas_localization import localization_result, localization_metrics\nfrom starlette.concurrency import run_in_threadpool\nimport asyncio\n')
s = s.replace('api_router = APIRouter(prefix="/api")', 'api_router = APIRouter(prefix="/api")\nscan_lock = asyncio.Lock()')
s = s.replace('    lsc, rsc = left["score"], right["score"]', '    if left.get("display_mode") == "localization" or right.get("display_mode") == "localization":\n        return localization_metrics(left, right)\n    lsc, rsc = left["score"], right["score"]')
# Legacy comparisons must not perform arithmetic against a newer null score.
s = s.replace('    if prev:\n        past = {', '    if prev and prev.get("metrics", {}).get("overall_score") is not None:\n        past = {')
a = s.index('    # Try a real sweep first', s.index('async def start_scan'))
b = s.index('    metrics = compute_metrics', a)
s = s[:a] + '''    # Serialize physical capture and move serial I/O / reconstruction off the
    # event loop so bridge/config requests remain responsive during acquisition.
    if scan_lock.locked():
        raise HTTPException(409, "A hardware scan is already running")
    async with scan_lock:
        hardware_capture = await run_in_threadpool(capture_real_hardware_sweep, cfg)
    if not hardware_capture:
        raise HTTPException(503, "No hardware capture available. Connect the wired scanner to produce DMAS-CF locations.")
    confident = bool((hardware_capture.get("dmas_snr") or {}).get("confident"))
    left = localization_result(hardware_capture.get("dmas_full_results", []), confident)
    # One acquisition is currently shared by the two UI views, not two measurements.
    right = {**left, "dots": list(left["dots"])}

''' + s[b:]
s = s.replace('        "hardware_capture": hardware_capture,', '        "hardware_capture": hardware_capture,\n        "display_mode": "localization",\n        "algorithm": "dmas-cf",\n        "capture_scope": "shared",')
s = s.replace('        "overall_score": s["metrics"]["overall_score"],', '        "display_mode": s.get("display_mode", "legacy"),\n        "left_dot_count": s["left"].get("dot_count"),\n        "right_dot_count": s["right"].get("dot_count"),\n        "overall_score": s["metrics"]["overall_score"],')
a = s.index('    """', s.index('async def recompute_threshold'))
b = s.index('\n\n@api_router.get("/scans")', a)
s = s[:a] + '''    raise HTTPException(410, "Severity threshold recomputation is retired. Capture a new DMAS-CF scan for reconstructed locations.")
''' + s[b:]
a = s.index('    delta = b["metrics"]', s.index('async def compare_scans'))
b = s.index('\n\n\n# ---------------------------------------------------------------------------', a)
s = s[:a] + '''    return {
        "a": {**scan_summary(a), "left_dots": a["left"]["dots"], "right_dots": a["right"]["dots"],
              "antennas": a.get("antennas", [])},
        "b": {**scan_summary(b), "left_dots": b["left"]["dots"], "right_dots": b["right"]["dots"],
              "antennas": b.get("antennas", [])},
        "deltas": {},
        "insight": "Compare reconstructed positions in the two domes. Marker counts and raw intensity are not health scores. Legacy severity dots are not displayed.",
    }
''' + s[b:]
p.write_text(s, encoding='utf-8')
print('Updated backend localization routing')
