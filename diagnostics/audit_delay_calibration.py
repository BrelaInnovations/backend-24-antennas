"""Audit saved delay calibration offline, without altering calibration or hardware."""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from core import calibration, geometry, timedomain


def trace_peaks(trace):
    f = np.asarray(trace['freqs'], dtype=float)*1e9
    s = np.asarray(trace['s21_real'])+1j*np.asarray(trace['s21_imag'])
    if len(f) != len(s) or len(f) < 3 or not np.all(np.isfinite(s)):
        raise ValueError('Invalid spectrum')
    if not np.allclose(np.diff(f), f[1]-f[0]):
        raise ValueError('Nonuniform frequency spacing')
    t, st = timedomain.to_time_domain(f, s)
    mag = np.abs(st)
    # Circular local maxima: IFFT time wraps with period 1/df.
    local = np.flatnonzero((mag >= np.roll(mag,1)) & (mag > np.roll(mag,-1)))
    selected = []
    period_ns = 1e9/(f[1]-f[0])
    for i in local[np.argsort(-mag[local])]:
        delay = float(t[i]*1e9)
        if all(min(abs(delay-p['delay_ns']),period_ns-abs(delay-p['delay_ns'])) >= 0.5 for p in selected):
            selected.append({'delay_ns':delay,'amplitude':float(mag[i])})
        if len(selected) == 3:
            break
    return {'peaks': selected, 'period_ns':period_ns, 'ifft_sample_ns':float((t[1]-t[0])*1e9), 'band_ghz':[float(f[0]/1e9),float(f[-1]/1e9)]}


def main():
    paths = [ROOT/'data/pair_delay_calibration.json',ROOT/'data/baseline_full_sweep.json',ROOT/'dataset/session_empty_1.json',ROOT/'dataset/session_empty_2.json']
    delay, *scans = [json.loads(p.read_text()) for p in paths]
    positions = geometry.physical_antenna_positions()
    usable = {p[2] for p in calibration.iter_usable_pairs(scans[0])}
    rows = []
    for label in sorted(delay):
        tx,rx = label.split('-')
        propagation_ns = np.linalg.norm(np.asarray(positions[tx])-positions[rx])/geometry.SPEED_OF_LIGHT_CM_PER_S*1e9
        expected_ns = delay[label]*1e9+propagation_ns
        measured = [trace_peaks(s[label]) for s in scans]
        observed = [m['peaks'][0]['delay_ns'] for m in measured]
        rows.append({'pair':label,'used':label in usable,'system_delay_ns':delay[label]*1e9,'expected_direct_peak_ns':expected_ns,'observed_peak_ns_baseline_empty1_empty2':observed,'baseline_mismatch_ns':observed[0]-expected_ns,'empty_peak_spread_ns':max(observed)-min(observed),'top_peaks':measured})
    components = {}
    for name in ['direct_thru_test','tx_isolation_test','rx_isolation_test','dualboard_tx1_rx1_open','dualboard_tx1_rx1__jumper']:
        p = ROOT/'dataset'/f'{name}.json'
        if p.exists():
            paths.append(p)
            components[name] = trace_peaks(json.loads(p.read_text()))
    mismatches = np.array([abs(r['baseline_mismatch_ns']) for r in rows])
    spreads = np.array([r['empty_peak_spread_ns'] for r in rows])
    summary = {'pairs':len(rows),'used_pairs':len(usable),'median_absolute_baseline_mismatch_ns':float(np.median(mismatches)),'max_absolute_baseline_mismatch_ns':float(max(mismatches)),'pairs_with_baseline_mismatch_over_0_25ns':int(sum(mismatches>0.25)),'pairs_with_empty_peak_spread_over_0_25ns':int(sum(spreads>0.25))}
    report = {'status':'Calibration is not independently verified; no offsets changed.', 'summary':summary,'pairs':rows,'historical_components':components,'input_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},'limitations':['The strongest peak may be direct coupling, multipath, or an instrument/reference-plane effect.','Component files lack wiring and calibration-reference metadata; they cannot be used to subtract component delays from current measurements.','0.25 ns is the reciprocal of the 4 GHz bandwidth, used only as a diagnostic flag, not a localization acceptance tolerance.','Zero padding refines time sampling but does not increase physical time resolution.']}
    (ROOT/'delay_calibration_audit.json').write_text(json.dumps(report,indent=2))
    lines = ['# Delay calibration audit','', '**Result: the current delay calibration cannot be independently verified from the saved files. No calibration values were changed.**','', 'The corrected reconstruction now includes cable/switch delay consistently. Remaining localization errors cannot be fixed by selecting the largest empty-scan peak and calling it direct propagation.','', '## Saved empty scans','',f"- Pairs examined: {len(rows)}; currently used: {len(usable)}.",f"- Median absolute baseline-peak mismatch: {np.median(mismatches):.3f} ns; maximum: {max(mismatches):.3f} ns.",f"- Pairs with mismatch above 0.25 ns: {sum(mismatches>0.25)}.",f"- Pairs whose dominant peak moves over 0.25 ns between baseline and two empty scans: {sum(spreads>0.25)}.",'','These are consistency checks, not proof of direct-path calibration. The 0.25 ns flag is a bandwidth-based diagnostic scale, not a 1 cm accuracy criterion.','','| Pair | Expected direct peak (ns) | Baseline strongest peak (ns) | Absolute mismatch (ns) | Used |','|---|---:|---:|---:|---|']
    for r in sorted(rows,key=lambda r:abs(r['baseline_mismatch_ns']),reverse=True)[:8]:
        lines.append(f"| {r['pair']} | {r['expected_direct_peak_ns']:.3f} | {r['observed_peak_ns_baseline_empty1_empty2'][0]:.3f} | {abs(r['baseline_mismatch_ns']):.3f} | {r['used']} |")
    lines += ['','## Historical component measurements','','| Saved file | Strongest peak (ns) |','|---|---:|']
    for name,info in components.items():
        lines.append(f"| {name} | {info['peaks'][0]['delay_ns']:.3f} |")
    lines += ['','These files do not record the exact wiring, terminations, or calibration reference planes. Comparing their peak times cannot establish which component caused an artifact, or provide a verified per-pair correction.','','## Required physical verification','','1. Record the current VNA calibration reference planes and actual port-to-antenna mapping.','2. Measure a known, characterized through connection between the selected TX and RX feed paths, replacing the antennas, while keeping both switch paths and feed cables in the measurement. Document the connection delay and exact wiring.','3. Repeat the connected measurement with the channel fixed, then after switching away and back. This separates repeatability from fixed path delay.','4. Start with TX1-RX1, then a flagged pair such as TX6-RX5. Extend calibration to other paths only after this method is checked.','5. Subtract the independently known through-connection delay to estimate the feed-chain delay. Antenna phase response remains a separate calibration requirement.','6. Reconnect the antennas, obtain a fresh baseline, and validate with target positions that were not used to fit calibration.','','Do not automatically overwrite the current 64 offsets using the strongest empty-dome peaks. No new hardware measurement was performed by this audit.']
    (ROOT/'delay_calibration_report.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps(summary,indent=2))
    print('Historical component peaks:',{n:round(x['peaks'][0]['delay_ns'],3) for n,x in components.items()})
    print('Saved delay_calibration_report.md and delay_calibration_audit.json')


if __name__ == '__main__':
    main()
