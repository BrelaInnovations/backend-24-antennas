"""
das_imaging.py -- compatibility shim.

The original monolithic das_imaging.py was split into core/geometry.py,
core/calibration.py, core/timedomain.py, and core/beamforming.py (see
README.md). This shim re-exports the same names so the scripts in
diagnostics/ -- written against the old module -- keep working
unmodified. New code should import from core/ directly instead.
"""
from core.geometry import (
    DOME_RADIUS_CM, ARM_ANGLES_DEG, ANTENNA_ARC_SPACING_CM, ANTENNAS_PER_ARM,
    SPEED_OF_LIGHT_CM_PER_S, physical_antenna_positions, tissue_velocity_cm_per_s,
    build_voxel_grid,
)
from core.calibration import (
    load_pair_delay_calibration, subtract_baseline, iter_usable_pairs as _iter_usable_pairs,
    EXCLUDE_SAME_INDEX_PAIRS, EXCLUDE_UNSTABLE_PHASE_PAIRS, EXCLUDE_WEAK_BASELINE_PAIRS,
)
from core.timedomain import to_time_domain
from core.beamforming import (
    run_reconstruction, snr_check, ASSUMED_PERMITTIVITY, estimate_tumor_extent,
)


def run_das(sweep_plot_data, resolution_cm=0.5, oversample=8,
            permittivity=ASSUMED_PERMITTIVITY, near_field_guard_cm=1.0,
            coherence_power=2.0, baseline_plot_data=None,
            min_freq_ghz=None, max_freq_ghz=None):
    """Alias -- old name for run_reconstruction(algo='das-cf', ...), the
    last validated working version from the original module."""
    return run_reconstruction(
        sweep_plot_data, algo="das-cf", resolution_cm=resolution_cm,
        oversample=oversample, permittivity=permittivity,
        near_field_guard_cm=near_field_guard_cm, coherence_power=coherence_power,
        baseline_plot_data=baseline_plot_data,
        min_freq_ghz=min_freq_ghz, max_freq_ghz=max_freq_ghz,
    )


def run_dmas_cf(sweep_plot_data, resolution_cm=0.5, oversample=8,
                 permittivity=ASSUMED_PERMITTIVITY, near_field_guard_cm=1.0,
                 coherence_power=2.0, baseline_plot_data=None,
                 min_freq_ghz=None, max_freq_ghz=None):
    """Alias -- old name for run_reconstruction(algo='dmas-cf', ...).
    Same signature/behavior pattern as run_das above, just DMAS-combined
    instead of plain DAS-summed."""
    return run_reconstruction(
        sweep_plot_data, algo="dmas-cf", resolution_cm=resolution_cm,
        oversample=oversample, permittivity=permittivity,
        near_field_guard_cm=near_field_guard_cm, coherence_power=coherence_power,
        baseline_plot_data=baseline_plot_data,
        min_freq_ghz=min_freq_ghz, max_freq_ghz=max_freq_ghz,
    )