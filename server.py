from fastapi import FastAPI, APIRouter, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import json
import math
import random
import logging
import uuid
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta

import hardware
import bridge_hardware
import scan_engine
import calibration
import das_imaging
import dot_scoring
from dmas_localization import localization_result, localization_metrics, localization_antennas
from starlette.concurrency import run_in_threadpool
import asyncio

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Same NanoVNA-Saver .cal file that used to be manually loaded before every
# GUI sweep. Put the file next to main.py (or update this path) -- if it's
# missing, real sweeps still run, just uncorrected (a warning is logged).
CALIBRATION_FILE = ROOT_DIR / "2-6_cal_with_new_cable.cal"

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

app = FastAPI(title="NaiBra API")
api_router = APIRouter(prefix="/api")
scan_lock = asyncio.Lock()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("naibra")


def now_iso():
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class AntennaCfg(BaseModel):
    id: str
    label: str
    enabled: bool = True
    freq_start_mhz: float = 2000.0
    freq_stop_mhz: float = 6000.0
    sweep_points: int = 101
    tx_power_dbm: float = -10.0
    gain_db: float = 0.0


class ProngCfg(BaseModel):
    index: int
    annotation: str
    antennas: List[AntennaCfg]


class PatchConfig(BaseModel):
    id: str = "main"
    num_prongs: int = 12
    antennas_per_prong: int = 4
    freq_start_mhz: float = 2000.0
    freq_stop_mhz: float = 6000.0
    sweep_points: int = 101
    connection_mode: str = "simulated"  # simulated | live
    transport: str = "simulated"  # simulated | bluetooth | wired
    bridge_device: str = ""
    device_name: str = "NanoVNA + SP48 Switch Matrix"
    prongs: List[ProngCfg] = []
    updated_at: str = Field(default_factory=now_iso)


class ConfigUpdate(BaseModel):
    num_prongs: Optional[int] = None
    antennas_per_prong: Optional[int] = None
    freq_start_mhz: Optional[float] = None
    freq_stop_mhz: Optional[float] = None
    sweep_points: Optional[int] = None
    connection_mode: Optional[str] = None
    transport: Optional[str] = None
    bridge_device: Optional[str] = None
    device_name: Optional[str] = None
    prongs: Optional[List[ProngCfg]] = None


class UserProfile(BaseModel):
    id: str = "main"
    name: str = ""
    age: Optional[int] = None
    height_cm: Optional[float] = None
    weight_kg: Optional[float] = None
    period_length: int = 5
    cycle_length: int = 28
    avatar_type: str = "kitten"  # kitten | puppy | bunny
    companion_name: str = ""
    mode: str = "user"  # user | developer
    updated_at: str = Field(default_factory=now_iso)


class UserUpdate(BaseModel):
    name: Optional[str] = None
    age: Optional[int] = None
    height_cm: Optional[float] = None
    weight_kg: Optional[float] = None
    period_length: Optional[int] = None
    cycle_length: Optional[int] = None
    avatar_type: Optional[str] = None
    companion_name: Optional[str] = None
    mode: Optional[str] = None


class PeriodLog(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    start_date: str  # YYYY-MM-DD
    notes: str = ""
    created_at: str = Field(default_factory=now_iso)


class PeriodCreate(BaseModel):
    start_date: str
    notes: str = ""


class ScanStart(BaseModel):
    label: Optional[str] = None


class ThresholdRecompute(BaseModel):
    sensitivity_db: float = Field(gt=0, le=30)


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

def build_prongs(num_prongs: int, per_prong: int, old_prongs: Optional[List[dict]] = None,
                 f_start=2000.0, f_stop=6000.0, points=101) -> List[dict]:
    old = {p["index"]: p for p in (old_prongs or [])}
    prongs = []
    for p in range(num_prongs):
        prev = old.get(p)
        antennas = []
        for a in range(per_prong):
            prev_ant = None
            if prev and a < len(prev.get("antennas", [])):
                prev_ant = prev["antennas"][a]
            if prev_ant:
                antennas.append(prev_ant)
            else:
                antennas.append({
                    "id": f"P{p + 1}A{a + 1}", "label": f"P{p + 1}-A{a + 1}", "enabled": True,
                    "freq_start_mhz": f_start, "freq_stop_mhz": f_stop,
                    "sweep_points": points, "tx_power_dbm": -10.0, "gain_db": 0.0,
                })
        prongs.append({
            "index": p,
            "annotation": prev["annotation"] if prev else f"Prong {p + 1}",
            "antennas": antennas,
        })
    return prongs


def default_config() -> dict:
    cfg = PatchConfig().model_dump()
    cfg["prongs"] = build_prongs(12, 4)
    return cfg


async def get_config_doc() -> dict:
    doc = await db.config.find_one({"id": "main"}, {"_id": 0})
    if not doc:
        doc = default_config()
        await db.config.insert_one({**doc})
        doc.pop("_id", None)
    return doc


# ---------------------------------------------------------------------------
# Geometry + scan simulation
# ---------------------------------------------------------------------------

def antenna_positions(cfg: dict) -> List[dict]:
    """Radial layout: prongs from apex, antennas along each prong on hemisphere surface."""
    out = []
    n = cfg["num_prongs"]
    for prong in cfg["prongs"]:
        theta = 2 * math.pi * prong["index"] / max(n, 1)
        per = len(prong["antennas"])
        for i, ant in enumerate(prong["antennas"]):
            polar = (i + 1) / (per + 1) * (math.pi / 2) * 0.94
            out.append({
                "id": ant["id"], "label": ant["label"], "prong": prong["index"],
                "annotation": prong["annotation"], "enabled": ant["enabled"],
                "x": round(math.sin(polar) * math.cos(theta), 4),
                "y": round(math.sin(polar) * math.sin(theta), 4),
                "z": round(math.cos(polar), 4),
            })
    return out


def _seg_point_dist(a, b, c):
    ab = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
    ac = (c[0] - a[0], c[1] - a[1], c[2] - a[2])
    ab2 = ab[0] ** 2 + ab[1] ** 2 + ab[2] ** 2
    t = 0.0 if ab2 == 0 else max(0.0, min(1.0, (ac[0] * ab[0] + ac[1] * ab[1] + ac[2] * ab[2]) / ab2))
    p = (a[0] + ab[0] * t, a[1] + ab[1] * t, a[2] + ab[2] * t)
    return math.dist(p, c)


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


def simulate_side(cfg: dict, rng: random.Random) -> dict:
    ants = [a for a in antenna_positions(cfg) if a["enabled"]]
    if len(ants) < 4:
        return {"dots": [], "score": 0, "mean_severity": 0, "anomaly_count": 0}

    n_anom = rng.choices([0, 1, 2], weights=[0.45, 0.40, 0.15])[0]
    anomalies = []
    for _ in range(n_anom):
        rr = rng.uniform(0.15, 0.55)
        th = rng.uniform(0, 2 * math.pi)
        anomalies.append({
            "c": (rr * math.cos(th), rr * math.sin(th), rng.uniform(0.15, 0.55)),
            "radius": rng.uniform(0.14, 0.28),
            "severity": rng.uniform(0.55, 1.0),
        })

    pts = [(a["x"], a["y"], a["z"]) for a in ants]
    lines = []
    for i in range(len(pts)):
        for j in range(i + 1, len(pts)):
            val = 0.10 + rng.random() * 0.20
            for an in anomalies:
                d = _seg_point_dist(pts[i], pts[j], an["c"])
                val += an["severity"] * math.exp(-((d / an["radius"]) ** 2) * 1.1)
            lines.append((i, j, min(1.0, val)))
    lines.sort(key=lambda ln: -ln[2])

    top = lines[:70]
    rest = lines[70:]
    if rest:
        top += rng.sample(rest, min(70, len(rest)))

    dots = []
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
            sev = max(0.0, min(1.0, (v1 + v2) / 2))
            dots.append({
                "x": round(mid[0], 3), "y": round(mid[1], 3), "z": round(mid[2], 3),
               "s": round(sev, 3), "c": _cat(sev), "region": region_label(mid[0], mid[1]),
            })
            if len(dots) >= 900:
                break
        if len(dots) >= 900:
            break

    dots.sort(key=lambda d: -d["s"])
    if len(dots) > 260:
        keep = dots[:110]
        keep += rng.sample(dots[110:], 150)
        dots = keep

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
        "anomaly_count": n_anom,
        "dot_counts": {
            "high": high_count,
            "medium": sum(1 for d in dots if d["c"] == "medium"),
            "low": sum(1 for d in dots if d["c"] == "low"),
            "baseline": sum(1 for d in dots if d["c"] == "baseline"),
        },
        "region_counts": r_breakdown,
        "worst_region": worst_region,
    }
    


def ring_antenna_positions(num_antennas: int = 12, ring_polar_deg: float = 62.0) -> List[dict]:
    polar = math.radians(ring_polar_deg)
    out = []
    for i in range(1, num_antennas + 1):
        theta = 2 * math.pi * (i - 1) / num_antennas
        out.append({
            "id": f"RA{i}", "label": f"Antenna {i}",
            "x": round(math.sin(polar) * math.cos(theta), 4),
            "y": round(math.sin(polar) * math.sin(theta), 4),
            "z": round(math.cos(polar), 4),
        })
    return out


def simulate_side_from_real_data(weights: Dict[str, float], num_antennas: int = 12) -> dict:
    """
    Real-data counterpart to simulate_side(). LEGACY as of the DAS-to-dots
    wiring below: start_scan() now calls dot_scoring.das_to_dome_result()
    for the actual dome dots when a DAS/DMAS-CF reconstruction succeeds.
    This heuristic is kept as the fallback path for when hardware captured
    a raw sweep but the DAS reconstruction itself failed/produced nothing
    -- see start_scan().
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


STANDARD_SCORE = 92  # standard healthy breast profile baseline


SCORE_DROP_ALERT_THRESHOLD = 15
SCORE_LOW_ALERT_THRESHOLD = 60

def check_alert(overall: int, prev):
    reasons = []
    if overall < SCORE_LOW_ALERT_THRESHOLD:
        reasons.append(f"Score {overall} is below the {SCORE_LOW_ALERT_THRESHOLD} safety threshold")
    if prev:
        delta = overall - prev["metrics"]["overall_score"]
        if delta <= -SCORE_DROP_ALERT_THRESHOLD:
            reasons.append(f"Score dropped {abs(delta)} points since your last scan ({prev['metrics']['overall_score']} \u2192 {overall})")
    return {"triggered": bool(reasons), "reasons": reasons}

def compute_metrics(left: dict, right: dict, prev: Optional[dict]) -> dict:
    if left.get("display_mode") == "localization" or right.get("display_mode") == "localization":
        return localization_metrics(left, right)
    lsc, rsc = left["score"], right["score"]
    asym = abs(lsc - rsc)
    overall = int(round((lsc + rsc) / 2 - min(12, asym * 0.4)))
    overall = max(20, min(99, overall))

    std_dev_l = round((STANDARD_SCORE - lsc) / STANDARD_SCORE * 100, 1)
    std_dev_r = round((STANDARD_SCORE - rsc) / STANDARD_SCORE * 100, 1)

    past = None
    if prev and prev.get("metrics", {}).get("overall_score") is not None:
        past = {
            "prev_scan_id": prev["id"],
            "prev_date": prev["created_at"],
            "prev_overall": prev["metrics"]["overall_score"],
            "delta": overall - prev["metrics"]["overall_score"],
            "left_delta": lsc - prev["left"]["score"],
            "right_delta": rsc - prev["right"]["score"],
        }

    if overall >= 80 and asym < 12:
        verdict, verdict_label = "healthy", "Healthy"
        recs = ["All clear! Keep up your monthly 1-minute scans.",
                "Next scan recommended on day 3 of your next cycle."]
    elif overall >= 60:
        verdict, verdict_label = "monitor", "Monitor"
        recs = ["Some elevated points detected. Re-scan in 7 days.",
                "Compare with your past profiles in the repository.",
                "Perform a self-exam using the guide in your profile."]
    else:
        verdict, verdict_label = "attention", "Needs Attention"
        recs = ["High-intensity region detected. Please consult a specialist.",
                "Export/share this profile with your physician.",
                "Re-scan to confirm — ensure the patch is well seated."]
    if asym >= 12:
        recs.insert(0, f"Left/right asymmetry of {asym} points detected — review both domes.")

    alert = check_alert(overall, prev)
    return {
        "overall_score": overall,
        "verdict": verdict,
        "verdict_label": verdict_label,
        "left_right": {"left": lsc, "right": rsc, "asymmetry": asym},
        "standard_vs_current": {"standard": STANDARD_SCORE, "left_deviation_pct": std_dev_l,
                                "right_deviation_pct": std_dev_r},
        "past_vs_current": past,
        "recommendations": recs,
        "alert": alert,
    }


def run_antenna_check(cfg: dict, rng: random.Random) -> List[dict]:
    results = []
    for a in antenna_positions(cfg):
        responding = a["enabled"] and rng.random() > 0.03
        results.append({
            "id": a["id"], "label": a["label"], "prong": a["prong"],
            "enabled": a["enabled"],
            "responding": responding,
            "return_loss_db": round(rng.uniform(-28, -12), 1) if responding else None,
            "latency_ms": round(rng.uniform(2, 14), 1) if responding else None,
        })
    return results


# ---------------------------------------------------------------------------
# Routes: config + antennas
# ---------------------------------------------------------------------------

class BridgeConnect(BaseModel):
    transport: str  # simulated | bluetooth | wired
    device: str = ""


@api_router.post("/bridge/scan")
async def bridge_scan():
    cfg = await get_config_doc()
    if cfg.get("transport", "simulated") == "simulated":
        rng = random.Random()
        devices = [
            {"id": "brela-vna-01", "name": "Brela NanoVNA Bridge", "rssi": rng.randint(-62, -40), "type": "bluetooth"},
            {"id": "nanovna-h4", "name": "NanoVNA-H4", "rssi": rng.randint(-80, -55), "type": "bluetooth"},
            {"id": "sp48-matrix", "name": "SP48 Switch Matrix", "rssi": rng.randint(-70, -48), "type": "bluetooth"},
        ]
        return {"devices": devices, "scanned_at": now_iso()}

    devices = bridge_hardware.discover_devices()
    return {"devices": devices, "scanned_at": now_iso()}


@api_router.post("/bridge/connect")
async def bridge_connect(body: BridgeConnect):
    cfg = await get_config_doc()
    cfg["transport"] = body.transport
    cfg["bridge_device"] = body.device
    cfg["updated_at"] = now_iso()

    if body.transport == "wired":
        result = bridge_hardware.test_wired_connection()
        cfg["connection_mode"] = "live" if result["connected"] else "simulated"
        await db.config.replace_one({"id": "main"}, cfg, upsert=True)
        return {
            "connected": result["connected"],
            "transport": body.transport,
            "device": result["vna_port"] or body.device,
            "link_quality": 100 if result["connected"] else 0,
            "firmware": "brela-bridge v0.9.2",
            "detail": result["detail"],
        }

    cfg["connection_mode"] = "simulated" if body.transport == "simulated" else "live"
    await db.config.replace_one({"id": "main"}, cfg, upsert=True)
    rng = random.Random()
    return {
        "connected": body.transport != "simulated",
        "transport": body.transport,
        "device": body.device,
        "link_quality": rng.randint(82, 99) if body.transport != "simulated" else 100,
        "firmware": "brela-bridge v0.9.2",
    }


@api_router.get("/bridge/status")
async def bridge_status():
    cfg = await get_config_doc()
    transport = cfg.get("transport", "simulated")

    if transport == "wired":
        result = bridge_hardware.test_wired_connection()
        return {
            "transport": transport,
            "device": result["vna_port"] or cfg.get("bridge_device", ""),
            "connected": result["connected"],
            "link_quality": 100 if result["connected"] else 0,
            "firmware": "brela-bridge v0.9.2",
            "device_name": cfg.get("device_name", ""),
            "detail": result["detail"],
        }

    rng = random.Random()
    connected = transport != "simulated"
    return {
        "transport": transport,
        "device": cfg.get("bridge_device", ""),
        "connected": connected,
        "link_quality": rng.randint(82, 99) if connected else 100,
        "firmware": "brela-bridge v0.9.2",
        "device_name": cfg.get("device_name", ""),
    }


@api_router.get("/")
async def root():
    return {"message": "NaiBra API", "status": "ok"}


@api_router.get("/config")
async def get_config():
    return await get_config_doc()


@api_router.put("/config")
async def update_config(body: ConfigUpdate):
    cfg = await get_config_doc()
    data = body.model_dump(exclude_none=True)
    geometry_changed = False
    for k in ("num_prongs", "antennas_per_prong"):
        if k in data and data[k] != cfg[k]:
            geometry_changed = True
    if "num_prongs" in data:
        data["num_prongs"] = max(4, min(16, data["num_prongs"]))
    if "antennas_per_prong" in data:
        data["antennas_per_prong"] = max(1, min(4, data["antennas_per_prong"]))
    cfg.update({k: v for k, v in data.items() if k != "prongs"})
    if "prongs" in data and not geometry_changed:
        cfg["prongs"] = data["prongs"]
    if geometry_changed:
        cfg["prongs"] = build_prongs(cfg["num_prongs"], cfg["antennas_per_prong"], cfg["prongs"],
                                     cfg["freq_start_mhz"], cfg["freq_stop_mhz"], cfg["sweep_points"])
    cfg["updated_at"] = now_iso()
    await db.config.replace_one({"id": "main"}, cfg, upsert=True)
    cfg.pop("_id", None)
    return cfg


@api_router.post("/config/reset")
async def reset_config():
    cfg = default_config()
    await db.config.replace_one({"id": "main"}, cfg, upsert=True)
    cfg.pop("_id", None)
    return cfg


@api_router.get("/antenna/layout")
async def antenna_layout():
    cfg = await get_config_doc()
    return {"antennas": antenna_positions(cfg), "num_prongs": cfg["num_prongs"],
            "antennas_per_prong": cfg["antennas_per_prong"]}


@api_router.post("/antenna/test")
async def antenna_test():
    cfg = await get_config_doc()
    rng = random.Random()
    results = run_antenna_check(cfg, rng)
    responding = sum(1 for r in results if r["responding"])
    total_enabled = sum(1 for r in results if r["enabled"])
    doc = {
        "id": str(uuid.uuid4()), "tested_at": now_iso(), "results": results,
        "responding": responding, "total_enabled": total_enabled,
        "all_ok": responding == total_enabled,
    }
    await db.antenna_tests.insert_one({**doc})
    doc.pop("_id", None)
    return doc


# ---------------------------------------------------------------------------
# Routes: scans
# ---------------------------------------------------------------------------

BASELINE_SENSITIVITY_DB = 6.0


def compute_weights_from_baseline(raw_s21_db: Dict[str, float], baseline_raw: Dict[str, float],
                                   sensitivity_db: float = BASELINE_SENSITIVITY_DB) -> Dict[str, float]:
    weights: Dict[str, float] = {}
    for label, cur_db in raw_s21_db.items():
        base_db = baseline_raw.get(label)
        if base_db is None:
            weights[label] = 0.0
            continue
        delta_db = abs(cur_db - base_db)
        weights[label] = max(0.0, min(1.0, delta_db / sensitivity_db))
    return weights


FULL_BASELINE_FILE = ROOT_DIR / hardware.DATA_DIR / "baseline_full_sweep.json"


def save_baseline_full_sweep(sweep_plot_data: dict) -> None:
    os.makedirs(FULL_BASELINE_FILE.parent, exist_ok=True)
    with open(FULL_BASELINE_FILE, "w") as f:
        json.dump(sweep_plot_data, f)


def load_baseline_full_sweep() -> Optional[dict]:
    if not FULL_BASELINE_FILE.exists():
        return None
    try:
        with open(FULL_BASELINE_FILE, "r") as f:
            return json.load(f)
    except Exception:
        logger.exception("Failed to load full-sweep baseline from %s", FULL_BASELINE_FILE)
        return None


def subtract_baseline_sweep(sweep_data: dict, baseline_sweep: dict) -> dict:
    diffed: Dict[str, dict] = {}
    for label, cur in sweep_data.items():
        cur_re = cur.get("s21_real") or []
        cur_im = cur.get("s21_imag") or []
        base = baseline_sweep.get(label)
        if not base or not cur_re:
            diffed[label] = {"freqs": cur.get("freqs", []), "s21_real": [], "s21_imag": []}
            continue
        base_re = base.get("s21_real") or []
        base_im = base.get("s21_imag") or []
        n = min(len(cur_re), len(base_re))
        diffed[label] = {
            "freqs": cur.get("freqs", [])[:n],
            "s21_real": [cur_re[i] - base_re[i] for i in range(n)],
            "s21_imag": [cur_im[i] - base_im[i] for i in range(n)],
        }
    return diffed


def capture_real_hardware_sweep(cfg: dict) -> Optional[dict]:
    if cfg.get("transport") != "wired":
        return None

    detected = hardware.auto_detect_devices()
    tx_port, rx_port, _cfg = hardware.resolve_tx_rx_ports(detected["switch_ports"])
    if not detected["vna_port"] or not tx_port or not rx_port:
        return None

    vna_ser = tx_ser = rx_ser = None
    try:
        vna_ser, _b1, _e1 = hardware.open_serial_connection_with_fallbacks(
            detected["vna_port"], "Auto", "VNA")
        tx_ser, _b2, _e2 = hardware.open_serial_connection_with_fallbacks(
            tx_port, "Auto", "TX")
        rx_ser, _b3, _e3 = hardware.open_serial_connection_with_fallbacks(
            rx_port, "Auto", "RX")
        if not (vna_ser and tx_ser and rx_ser):
            return None

        num_antennas = 12  # current physical antenna count (16->24 antenna upgrade)
        start_hz = int(cfg.get("freq_start_mhz", 2000.0) * 1e6)
        stop_hz = int(cfg.get("freq_stop_mhz", 6000.0) * 1e6)
        points = min(int(cfg.get("sweep_points", 101)), 51)    # keep it quick for now

        cal = None
        calibrated = False
        if CALIBRATION_FILE.exists():
            try:
                cal = calibration.get_calibration(str(CALIBRATION_FILE))
                calibrated = True
            except Exception:
                logger.exception("Failed to load calibration file %s -- running uncorrected", CALIBRATION_FILE)
        else:
            logger.warning("Calibration file not found at %s -- running uncorrected", CALIBRATION_FILE)

        NUM_SWEEP_AVERAGES = 3

        def _run_averaged_sweep_set() -> dict:
            """NUM_SWEEP_AVERAGES repeated sweeps, median-combined via average_sweeps()."""
            raw_sweeps = []
            for _ in range(NUM_SWEEP_AVERAGES):
                raw_sweeps.append(scan_engine.run_full_sweep(
                    vna_ser, tx_ser, rx_ser, start_hz, stop_hz,
                    num_antennas=num_antennas, points=points, calibration=cal,
                ))
            return scan_engine.average_sweeps(raw_sweeps)

        sweep_data = _run_averaged_sweep_set()

        weights, raw_values = scan_engine.compute_sensor_weights_from_traces(sweep_data)

        baseline_raw = load_baseline_raw()
        if baseline_raw:
            weights = compute_weights_from_baseline(raw_values, baseline_raw)
            weight_method = "baseline_delta"
        else:
            weight_method = "min_max_no_baseline"

        baseline_full = load_baseline_full_sweep()
        das_baseline_used = baseline_full is not None
        das_input = subtract_baseline_sweep(sweep_data, baseline_full) if baseline_full else sweep_data
        try:
            das_results_tissue = das_imaging.run_das(das_input, resolution_cm=0.5, oversample=8,
                                                      permittivity=das_imaging.ASSUMED_PERMITTIVITY)
            das_results_air = das_imaging.run_das(das_input, resolution_cm=0.5, oversample=8,
                                                   permittivity=1.0)
            das_top_candidates = das_results_tissue[:5]
            das_extent = das_imaging.estimate_tumor_extent(das_results_tissue, threshold_fraction=0.5,
                                                            resolution_cm=0.5) if das_results_tissue else None
            das_top_candidates_air = das_results_air[:5]

            das_extent_air = das_imaging.estimate_tumor_extent(das_results_air, threshold_fraction=0.5,
                                                    resolution_cm=0.5) if das_results_air else None
            das_snr = das_imaging.snr_check(das_results_tissue) if das_results_tissue else None
            das_snr_air = das_imaging.snr_check(das_results_air) if das_results_air else None

            dmas_results_tissue = das_imaging.run_dmas_cf(das_input, resolution_cm=0.5, oversample=8,
                                                           permittivity=das_imaging.ASSUMED_PERMITTIVITY)
            dmas_results_air = das_imaging.run_dmas_cf(das_input, resolution_cm=0.5, oversample=8,
                                                        permittivity=1.0)
            dmas_top_candidates = dmas_results_tissue[:5]
            dmas_extent = das_imaging.estimate_tumor_extent(dmas_results_tissue, threshold_fraction=0.5,
                                                             resolution_cm=0.5) if dmas_results_tissue else None
            dmas_top_candidates_air = dmas_results_air[:5]
            dmas_extent_air = das_imaging.estimate_tumor_extent(dmas_results_air, threshold_fraction=0.5,
                                                    resolution_cm=0.5) if dmas_results_air else None
            dmas_snr = das_imaging.snr_check(dmas_results_tissue) if dmas_results_tissue else None
            dmas_snr_air = das_imaging.snr_check(dmas_results_air) if dmas_results_air else None

        except Exception:
            logger.exception("DAS reconstruction failed -- continuing without a location estimate")
            das_top_candidates = []
            das_extent = None
            das_top_candidates_air = []
            das_extent_air = None
            das_snr = None
            das_snr_air = None
            dmas_top_candidates = []
            dmas_results_tissue = []
            dmas_extent = None
            dmas_top_candidates_air = []
            dmas_extent_air = None
            dmas_snr = None
            dmas_snr_air = None

        return {
            "num_antennas": num_antennas,
            "freq_start_mhz": cfg.get("freq_start_mhz"),
            "freq_stop_mhz": cfg.get("freq_stop_mhz"),
            "points_per_sweep": points,
            "calibrated": calibrated,
            "weight_method": weight_method,
            "weights": weights,
            "raw_s21_db": raw_values,
            "das_baseline_used": das_baseline_used,
            "das_top_location": das_top_candidates[0] if das_top_candidates else None,
            "das_top_candidates": das_top_candidates,
            "das_extent": das_extent,
            "das_top_location_air_assumption": das_top_candidates_air[0] if das_top_candidates_air else None,
            "dmas_top_location": dmas_top_candidates[0] if dmas_top_candidates else None,
            "dmas_top_candidates": dmas_top_candidates,
            # Full (untruncated) voxel list -- NOT the [:5] slice above.
            # das_to_dome_result() needs the whole reconstructed field to
            # threshold into a real cluster of dots around the target;
            # dmas_top_candidates stays as the separate top-5 "candidate
            # locations" field used elsewhere in the response.
            "dmas_full_results": dmas_results_tissue,
            "dmas_extent": dmas_extent,
            "dmas_top_location_air_assumption": dmas_top_candidates_air[0] if dmas_top_candidates_air else None,
            "sweep_plot_data": sweep_data,
            "das_extent_air": das_extent_air,
            "das_snr": das_snr,
            "das_snr_air": das_snr_air,
            "dmas_extent_air": dmas_extent_air,
            "dmas_snr": dmas_snr,
            "dmas_snr_air": dmas_snr_air,
        }
    except Exception:
        logger.exception("Real hardware sweep failed")
        return None
    finally:
        for s in (vna_ser, tx_ser, rx_ser):
            try:
                if s and s.is_open:
                    s.close()
            except Exception:
                pass


BASELINE_FILE = ROOT_DIR / hardware.DATA_DIR / "baseline_raw_s21.json"


def save_baseline_raw(raw_s21_db: Dict[str, float]) -> None:
    os.makedirs(BASELINE_FILE.parent, exist_ok=True)
    with open(BASELINE_FILE, "w") as f:
        json.dump(raw_s21_db, f, indent=2)


def load_baseline_raw() -> Optional[Dict[str, float]]:
    if not BASELINE_FILE.exists():
        return None
    try:
        with open(BASELINE_FILE, "r") as f:
            return json.load(f)
    except Exception:
        logger.exception("Failed to load baseline raw S21 from %s", BASELINE_FILE)
        return None


@api_router.post("/calibration/baseline")
async def capture_baseline():
    cfg = await get_config_doc()
    if scan_lock.locked():
        raise HTTPException(409, "A hardware scan is already running")
    async with scan_lock:
        capture = await run_in_threadpool(capture_real_hardware_sweep, cfg)
    if not capture or not capture.get("raw_s21_db"):
        raise HTTPException(
            status_code=503,
            detail="Could not capture a real hardware sweep -- check the device is "
                   "connected and transport is set to 'wired'.",
        )
    save_baseline_raw(capture["raw_s21_db"])
    if capture.get("sweep_plot_data"):
        save_baseline_full_sweep(capture["sweep_plot_data"])
    return {
        "saved": True,
        "path": str(BASELINE_FILE),
        "full_sweep_path": str(FULL_BASELINE_FILE),
        "num_pairs": len(capture["raw_s21_db"]),
        "calibrated": capture.get("calibrated", False),
    }


@api_router.get("/calibration/baseline")
async def get_baseline_status():
    baseline = load_baseline_raw()
    if baseline is None:
        return {"exists": False}
    return {"exists": True, "path": str(BASELINE_FILE), "num_pairs": len(baseline)}


@api_router.post("/scan/start")
async def start_scan(body: ScanStart):
    cfg = await get_config_doc()

    # Serialize physical capture and move serial I/O / reconstruction off the
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

    metrics = localization_metrics(left, right)
    ants = localization_antennas()
    sequence = [a["id"] for a in ants if a["enabled"]]
    # No per-antenna diagnostic is performed by this acquisition endpoint.
    antenna_check = []

    # dmas_full_results (the whole reconstructed voxel grid -- thousands of
    # entries) was only needed above to compute left/right dots; drop it
    # before this gets persisted so every saved scan doc isn't bloated with
    # a full voxel dump that nothing downstream reads back.
    if hardware_capture and "dmas_full_results" in hardware_capture:
        hardware_capture = {k: v for k, v in hardware_capture.items() if k != "dmas_full_results"}

    scan = {
        "id": str(uuid.uuid4()),
        "created_at": now_iso(),
        "label": body.label or datetime.now(timezone.utc).strftime("Scan %b %d, %Y"),
        "left": left,
        "right": right,
        "metrics": metrics,
        "sequence": sequence,
        "antenna_check": antenna_check,
        "antennas": ants,
        "hardware_capture": hardware_capture,
        "display_mode": "localization",
        "algorithm": "dmas-cf",
        "capture_scope": "shared",
        "config_snapshot": {
            "num_prongs": cfg["num_prongs"], "antennas_per_prong": cfg["antennas_per_prong"],
            "freq_start_mhz": cfg["freq_start_mhz"], "freq_stop_mhz": cfg["freq_stop_mhz"],
            "sweep_points": cfg["sweep_points"], "connection_mode": cfg["connection_mode"],
        },
    }
    await db.scans.insert_one({**scan})
    scan.pop("_id", None)
    return scan


def scan_summary(s: dict) -> dict:
    return {
        "id": s["id"], "created_at": s["created_at"], "label": s["label"],
        "display_mode": s.get("display_mode", "legacy"),
        "left_dot_count": s["left"].get("dot_count"),
        "right_dot_count": s["right"].get("dot_count"),
        "overall_score": s["metrics"]["overall_score"],
        "verdict": s["metrics"]["verdict"],
        "verdict_label": s["metrics"]["verdict_label"],
        "left_score": s["left"]["score"], "right_score": s["right"]["score"],
        "left_counts": s["left"].get("dot_counts", {}),
        "right_counts": s["right"].get("dot_counts", {}),
        "asymmetry": s["metrics"]["left_right"]["asymmetry"],
    }


@api_router.post("/scans/{scan_id}/recompute-threshold")
async def recompute_threshold(scan_id: str, body: ThresholdRecompute):
    raise HTTPException(410, "Severity threshold recomputation is retired. Capture a new DMAS-CF scan for reconstructed locations.")


@api_router.get("/scans")
async def list_scans():
    docs = await db.scans.find({}, {"_id": 0, "left.dots": 0, "right.dots": 0,
                                    "sequence": 0, "antenna_check": 0, "antennas": 0,
                                    "hardware_capture": 0}) \
        .sort("created_at", -1).to_list(200)
    return [scan_summary(d) for d in docs]


@api_router.get("/scans/latest")
async def latest_scan():
    doc = await db.scans.find_one({}, {"_id": 0}, sort=[("created_at", -1)])
    if not doc:
        raise HTTPException(404, "No scans yet")
    return doc


@api_router.get("/scans/{scan_id}")
async def get_scan(scan_id: str):
    doc = await db.scans.find_one({"id": scan_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Scan not found")
    return doc


@api_router.delete("/scans/{scan_id}")
async def delete_scan(scan_id: str):
    res = await db.scans.delete_one({"id": scan_id})
    if res.deleted_count == 0:
        raise HTTPException(404, "Scan not found")
    return {"deleted": scan_id}


@api_router.get("/compare/{scan_a}/{scan_b}")
async def compare_scans(scan_a: str, scan_b: str):
    a = await db.scans.find_one({"id": scan_a}, {"_id": 0})
    b = await db.scans.find_one({"id": scan_b}, {"_id": 0})
    if not a or not b:
        raise HTTPException(404, "One or both scans not found")
    if a["created_at"] > b["created_at"]:
        a, b = b, a
    return {
        "a": {**scan_summary(a), "left_dots": a["left"]["dots"], "right_dots": a["right"]["dots"],
              "antennas": a.get("antennas", [])},
        "b": {**scan_summary(b), "left_dots": b["left"]["dots"], "right_dots": b["right"]["dots"],
              "antennas": b.get("antennas", [])},
        "deltas": {},
        "insight": "Compare reconstructed positions in the two domes. Marker counts and raw intensity are not health scores. Legacy severity dots are not displayed.",
    }



# ---------------------------------------------------------------------------
# Routes: user / periods / avatar
# ---------------------------------------------------------------------------

async def get_user_doc() -> dict:
    doc = await db.users.find_one({"id": "main"}, {"_id": 0})
    if not doc:
        doc = UserProfile().model_dump()
        await db.users.insert_one({**doc})
        doc.pop("_id", None)
    return doc


@api_router.get("/user")
async def get_user():
    return await get_user_doc()


@api_router.put("/user")
async def update_user(body: UserUpdate):
    user = await get_user_doc()
    user.update(body.model_dump(exclude_none=True))
    user["updated_at"] = now_iso()
    await db.users.replace_one({"id": "main"}, user, upsert=True)
    user.pop("_id", None)
    return user


@api_router.get("/periods")
async def list_periods():
    return await db.periods.find({}, {"_id": 0}).sort("start_date", -1).to_list(100)


@api_router.post("/periods")
async def create_period(body: PeriodCreate):
    try:
        datetime.strptime(body.start_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(422, "start_date must be YYYY-MM-DD")
    existing = await db.periods.find_one({"start_date": body.start_date})
    if existing:
        raise HTTPException(409, "Period already logged for this date")
    log = PeriodLog(start_date=body.start_date, notes=body.notes).model_dump()
    await db.periods.insert_one({**log})
    log.pop("_id", None)
    return log


@api_router.delete("/periods/{period_id}")
async def delete_period(period_id: str):
    res = await db.periods.delete_one({"id": period_id})
    if res.deleted_count == 0:
        raise HTTPException(404, "Not found")
    return {"deleted": period_id}


@api_router.get("/cycle/status")
async def cycle_status():
    user = await get_user_doc()
    periods = await db.periods.find({}, {"_id": 0}).sort("start_date", -1).to_list(1)
    if not periods:
        return {"has_data": False, "cycle_day": None, "is_test_day": False,
                "next_period_date": None, "next_test_date": None, "days_until_period": None,
                "last_period": None, "period_length": user["period_length"],
                "cycle_length": user["cycle_length"]}
    last = periods[0]
    last_start = datetime.strptime(last["start_date"], "%Y-%m-%d").date()
    today = datetime.now(timezone.utc).date()
    cycle_day = (today - last_start).days % user["cycle_length"] + 1 \
        if (today - last_start).days >= 0 else None
    raw_day = (today - last_start).days + 1
    next_period = last_start + timedelta(days=user["cycle_length"])
    while next_period <= today:
        next_period += timedelta(days=user["cycle_length"])
    next_test = next_period + timedelta(days=2) if raw_day > 3 else last_start + timedelta(days=2)
    return {
        "has_data": True,
        "cycle_day": cycle_day,
        "raw_day": raw_day,
        "is_test_day": cycle_day == 3,
        "in_period": raw_day is not None and 1 <= raw_day <= user["period_length"],
        "next_period_date": next_period.isoformat(),
        "days_until_period": (next_period - today).days,
        "next_test_date": next_test.isoformat(),
        "last_period": last,
        "period_length": user["period_length"],
        "cycle_length": user["cycle_length"],
    }


AVATAR_STAGES = ["Newborn", "Baby", "Junior", "Bloom", "Radiant"]


@api_router.get("/avatar/status")
async def avatar_status():
    user = await get_user_doc()
    scans = await db.scans.find({}, {"_id": 0, "created_at": 1}).sort("created_at", 1).to_list(500)
    months = sorted({s["created_at"][:7] for s in scans})
    stage = min(4, len(months))
    last_days = None
    if scans:
        last_dt = datetime.fromisoformat(scans[-1]["created_at"])
        last_days = (datetime.now(timezone.utc) - last_dt).days
    if last_days is None:
        mood, mood_msg = "waiting", "Your companion is waiting for your first scan!"
    elif last_days <= 31:
        mood, mood_msg = "happy", "Fed and thriving — you scanned this month! 💕"
    elif last_days <= 45:
        mood, mood_msg = "hungry", "Getting hungry... time for your monthly scan."
    else:
        mood, mood_msg = "sad", "Withering... a scan will bring the sparkle back."
    return {
        "avatar_type": user["avatar_type"],
        "stage": stage,
        "stage_name": AVATAR_STAGES[stage],
        "stages": AVATAR_STAGES,
        "months_active": months,
        "mood": mood,
        "mood_message": mood_msg,
        "last_scan_days_ago": last_days,
        "total_scans": len(scans),
    }


app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
