"""
geometry.py -- physical antenna array geometry.

Perfect hemisphere dome, radius = 8 cm. 6 antenna arms (3 RX + 3 TX),
each with 4 antennas, spaced 3.0 cm apart along the curved surface
(arc length) from the apex: 3.0, 6.0, 9.0, 12.0 cm. 24 antennas total
(12 RX + 12 TX), updated from the earlier 16-antenna (8 RX + 8 TX) array.
  RX1-4 arm at 60 deg,   RX5-8 arm at 0 deg,   RX9-12 arm at 300 deg
  TX1-4 arm at 240 deg,  TX5-8 arm at 180 deg, TX9-12 arm at 120 deg
Antenna N within an arm: N=1 nearest apex, N=4 nearest the base/edge.
Coordinate convention clarified by the user on 2026-09-08: +X points
between RX5 and TX1. Reading the supplied upright photograph as a top
view, +Y points between the two TX arms; +Z is above the base plane.
The two TX arms are adjacent, as are the two RX arms. Radius and arc
spacing remain the existing idealized model, not photo measurements.
Port-to-antenna cable continuity has not been verified from the photo.
NOTE: the "+X between RX5 and TX1" convention above was written for the
old 16-antenna layout and has not been re-verified against the new
RX9-12/TX9-12 arms -- re-check against the physical dome if the absolute
+X/+Y orientation (not just the DAS output) matters for your use case.
"""
from __future__ import annotations
import math
from typing import Dict, Tuple

DOME_RADIUS_CM = 8.5
ARM_ANGLES_DEG = {
    "RX_A": 60.0,    # RX1-4
    "RX_B": 0.0,     # RX5-8
    "RX_C": 300.0,   # RX9-12
    "TX_A": 240.0,   # TX1-4
    "TX_B": 180.0,   # TX5-8
    "TX_C": 120.0,   # TX9-12
}
CENTER_TO_FIRST_ANTENNA_CM = 3.0 # apex -> antenna 1 (different from the between-antenna gap)
ANTENNA_ARC_SPACING_CM = 3.0      # antenna N -> antenna N+1
ANTENNAS_PER_ARM = 4

SPEED_OF_LIGHT_CM_PER_S = 2.998e10  # cm/s


def _arm_antenna_position(arm_angle_deg: float, antenna_index: int) -> Tuple[float, float, float]:
    """3D position (cm), hemisphere apex at (0,0,R), base plane at z=0.
    Idealized fallback only -- see physical_antenna_positions().

    antenna_index=1 sits CENTER_TO_FIRST_ANTENNA_CM from the apex; every
    antenna after that is ANTENNA_ARC_SPACING_CM further along the arm --
    these are two different distances, not one uniform spacing."""
    arc_length_cm = CENTER_TO_FIRST_ANTENNA_CM + (antenna_index - 1) * ANTENNA_ARC_SPACING_CM
    theta = arc_length_cm / DOME_RADIUS_CM
    phi = math.radians(arm_angle_deg)
    x = DOME_RADIUS_CM * math.sin(theta) * math.cos(phi)
    y = DOME_RADIUS_CM * math.sin(theta) * math.sin(phi)
    z = DOME_RADIUS_CM * math.cos(theta)
    return (round(x, 4), round(y, 4), round(z, 4))


def physical_antenna_positions() -> Dict[str, Tuple[float, float, float]]:
    """Returns {"TX1": (x,y,z), ..., "RX12": (...)} in cm, apex at (0,0,8)."""
    positions: Dict[str, Tuple[float, float, float]] = {}
    for i in range(1, ANTENNAS_PER_ARM + 1):
        positions[f"RX{i}"] = _arm_antenna_position(ARM_ANGLES_DEG["RX_A"], i)
        positions[f"RX{i + 4}"] = _arm_antenna_position(ARM_ANGLES_DEG["RX_B"], i)
        positions[f"RX{i + 8}"] = _arm_antenna_position(ARM_ANGLES_DEG["RX_C"], i)
        positions[f"TX{i}"] = _arm_antenna_position(ARM_ANGLES_DEG["TX_A"], i)
        positions[f"TX{i + 4}"] = _arm_antenna_position(ARM_ANGLES_DEG["TX_B"], i)
        positions[f"TX{i + 8}"] = _arm_antenna_position(ARM_ANGLES_DEG["TX_C"], i)
    return positions


def tissue_velocity_cm_per_s(permittivity: float) -> float:
    """EM wave speed: v = c / sqrt(permittivity). Pass 1.0 for air (current
    bench-test phase, no coupling medium, metal/hand targets)."""
    return SPEED_OF_LIGHT_CM_PER_S / math.sqrt(permittivity)


def build_voxel_grid(resolution_cm: float = 0.5):
    """All voxels inside the hemisphere. No global 'exclude near any
    antenna' filter -- validated as throwing away real search volume
    unnecessarily; near-field protection is applied per-pair instead,
    inside beamforming.py."""
    import numpy as np
    r = DOME_RADIUS_CM
    coords_xy = np.arange(-r, r + resolution_cm, resolution_cm)
    coords_z = np.arange(0, r + resolution_cm, resolution_cm)
    xx, yy, zz = np.meshgrid(coords_xy, coords_xy, coords_z, indexing="ij")
    xx, yy, zz = xx.ravel(), yy.ravel(), zz.ravel()
    inside = xx**2 + yy**2 + zz**2 <= r**2
    return np.stack([xx[inside], yy[inside], zz[inside]], axis=1)
