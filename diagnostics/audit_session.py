"""Offline audit of session_* captures; never opens hardware or changes calibration."""
import json
import sys
from pathlib import Path
from itertools import combinations

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from core import beamforming, calibration, timedomain, geometry


def main():
    manifest = json.loads((ROOT / 'dataset/manifest.json').read_text())
    entries = [e for e in manifest if e['label'].startswith('session_')]
    baseline = json.loads((ROOT / 'data/baseline_full_sweep.json').read_text())
    scans = {e['label']: json.loads((ROOT / e['file']).read_text()) for e in entries}
    labels = sorted(baseline)
    usable = [p[2] for p in calibration.iter_usable_pairs(baseline)]
    def array(scan, pairs=labels):
        return np.array([np.asarray(scan[p]['s21_real']) + 1j*np.asarray(scan[p]['s21_imag']) for p in pairs])
    def rms(a):
        return float(np.sqrt(np.mean(np.abs(a)**2)))
    for name, scan in scans.items():
        assert set(scan) == set(baseline), name
        for p in labels:
            assert np.array_equal(scan[p]['freqs'], baseline[p]['freqs']), (name, p)
            assert len(scan[p]['s21_real']) == len(scan[p]['s21_imag']) == len(scan[p]['freqs'])
        assert np.isfinite(array(scan)).all(), name
    delays = calibration.load_pair_delay_calibration()
    report = {'gate_reference': 'propagation time excluding per-pair system delay', 'usable_pairs': len(usable), 'system_delay_ns_range': [min(delays.values())*1e9, max(delays.values())*1e9], 'scans': {}, 'differences': {}}
    positions = geometry.physical_antenna_positions()
    peak_checks = {}
    for p in labels:
        tx, rx = p.split('-')
        d = baseline[p]
        t, signal = timedomain.to_time_domain(np.array(d['freqs'])*1e9, array(baseline,[p])[0])
        observed = float(t[np.argmax(np.abs(signal))]*1e9)
        expected = (delays[p]+np.linalg.norm(np.array(positions[tx])-positions[rx])/geometry.SPEED_OF_LIGHT_CM_PER_S)*1e9
        peak_checks[p] = {'baseline_strongest_peak_ns': observed, 'calibrated_direct_path_ns': float(expected), 'difference_ns': float(observed-expected)}
    report['baseline_delay_consistency'] = peak_checks
    report['calibration_caveat'] = 'Agreement with the strongest baseline peak does not establish that it is direct coupling rather than multipath.'
    for e in entries:
        name = e['label']
        row = {'truth_cm': None if 'empty' in name else e['true_position_cm'], 'residual_rms_all_pairs': rms(array(scans[name])-array(baseline)), 'reconstruction': {}}
        for gate_name, gate in [('default_gate', 1.2), ('gate_disabled_diagnostic', None)]:
            for algo in ['das', 'das-cf', 'dmas', 'dmas-cf']:
                results = beamforming.run_reconstruction(scans[name], baseline_plot_data=baseline, algo=algo, artifact_gate_ns=gate)
                peak = results[0] if results else None
                pos = [peak[k] for k in ['x','y','z']] if peak else None
                valid = peak is not None and peak['intensity'] > 0
                item = {'position_cm': pos if valid else None, 'peak_intensity': peak['intensity'] if peak else 0., 'no_candidate': not valid, 'confidence': beamforming.snr_check(results)}
                if not np.isfinite(item['confidence']['peak_to_mean_ratio']):
                    item['confidence']['peak_to_mean_ratio'] = None
                if row['truth_cm'] is not None and valid:
                    item['error_cm'] = float(np.linalg.norm(np.array(pos)-row['truth_cm']))
                row['reconstruction'][gate_name + '/' + algo] = item
        report['scans'][name] = row
        print(name, json.dumps(row['reconstruction']['default_gate/das-cf']), flush=True)
    for a,b in combinations(scans,2):
        report['differences'][a+' vs '+b] = {'rms_all_pairs': rms(array(scans[a])-array(scans[b])), 'rms_usable_pairs': rms(array(scans[a],usable)-array(scans[b],usable))}
    a_names = [n for n in scans if n.startswith('session_A')]
    if len(a_names) >= 2 and 'session_B' in scans:
        av = np.array([array(scans[n],usable) for n in a_names])
        report['A_repeat_rms_about_mean'] = rms(av-av.mean(axis=0))
        report['B_minus_A_mean_rms'] = rms(array(scans['session_B'],usable)-av.mean(axis=0))
    report_path = ROOT/'session_audit_after_timing_fix.json'
    report_path.write_text(json.dumps(report,indent=2,allow_nan=False))
    print('SUMMARY', json.dumps({k:v for k,v in report.items() if k not in ('scans', 'baseline_delay_consistency', 'differences')}))
    print('Baseline peak/calibrated direct delay absolute mismatch ns: median/max', np.median([abs(p['difference_ns']) for p in peak_checks.values()]), max(abs(p['difference_ns']) for p in peak_checks.values()))
    print('Saved',report_path)


if __name__ == '__main__':
    main()
