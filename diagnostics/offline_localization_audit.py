"""Reproducible offline sensitivity audit; no calibration fitting or hardware calls."""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from core import beamforming, calibration, geometry


def main():
    control = sorted((ROOT/'dataset').glob('empty_control_*'))[-1]
    files = {'A':control/'baseline_reference.json', 'B':ROOT/'data/baseline_full_sweep.json'}
    bases = {k:json.loads(p.read_text()) for k,p in files.items()}
    positions = geometry.physical_antenna_positions()
    voxels = geometry.build_voxel_grid()
    delay = calibration.load_pair_delay_calibration()
    velocity = geometry.tissue_velocity_cm_per_s(1.0)
    report = {'algorithm':'dmas-cf','z_reference_cm':2.5,'z_note':'User-confirmed for A; assumed same cube/support for B.', 'baseline_sources':{k:str(p.relative_to(ROOT)) for k,p in files.items()},'baseline_sha256':{k:hashlib.sha256(p.read_bytes()).hexdigest() for k,p in files.items()},'scans':{},'notes':['B baseline association is inferred from reproducing saved PNG results; scans lack embedded calibration provenance.','Leave-one-antenna-out is a sensitivity test, not an accuracy guarantee or independent repeated measurement.','Alternative baselines are a stress test, not an approved correction.','No channels, offsets, geometry, or thresholds were optimized using target labels.']}
    entries = [e for e in json.loads((ROOT/'dataset/manifest.json').read_text()) if e['label'].startswith(('single_A','single_B'))]
    def combine(c):
        summed = c.sum(0)
        cf = beamforming._coherence_factor(c,summed,len(c))
        return abs(beamforming._dmas_combine(c))*cf**2
    for entry in entries:
        name = entry['label']; group = 'A' if name.startswith('single_A') else 'B'
        scan = json.loads((ROOT/entry['file']).read_text())
        for label,d in scan.items():
            if len(d['freqs']) != 101 or len(d['s21_real']) != 101 or len(d['s21_imag']) != 101:
                raise ValueError(f'Incomplete scan: {name} {label}')
            if not np.allclose(d['freqs'],np.linspace(2,6,101)):
                raise ValueError(f'Frequency mismatch: {name} {label}')
            if not np.isfinite(d['s21_real']+d['s21_imag']).all():
                raise ValueError(f'Nonfinite data: {name} {label}')
        residual = calibration.subtract_baseline(scan,bases[group])
        c,count,labels = beamforming._gather_pair_contributions(residual,voxels,positions,velocity,delay,8,1.0)
        intensity = combine(c);i=int(np.argmax(intensity));peak=voxels[i]
        full = beamforming.run_reconstruction(scan,baseline_plot_data=bases[group],algo='dmas-cf')
        # Validate the fast sensitivity calculation against the production path.
        assert np.allclose(peak,[full[0][k] for k in ('x','y','z')])
        assert np.isclose(intensity[i],full[0]['intensity'],rtol=1e-10,atol=1e-20)
        truth = np.array([*entry['true_position_cm'][:2],2.5])
        truth_idx = int(np.argmin(np.linalg.norm(voxels-truth,axis=1)))
        outside = np.linalg.norm(voxels-peak,axis=1)>=2.0
        competitor=int(np.argmax(np.where(outside,intensity,-np.inf)))
        leave_out=[]
        for antenna in positions:
            keep = [antenna not in label.split('-') for label in labels]
            scores=combine(c[keep]);loc=voxels[int(np.argmax(scores))]
            leave_out.append({'removed_antenna':antenna,'candidate_cm':loc.tolist(),'shift_from_full_cm':float(np.linalg.norm(loc-peak))})
        other='B' if group=='A' else 'A'
        alternative=beamforming.run_reconstruction(scan,baseline_plot_data=bases[other],algo='dmas-cf')[0]
        altpos=np.array([alternative[k] for k in ('x','y','z')])
        row={'truth_cm':truth.tolist(),'candidate_cm':peak.tolist(),'error_cm':float(np.linalg.norm(peak-truth)),'confidence':beamforming.snr_check(full),'competitor_at_least_2cm_away':{'candidate_cm':voxels[competitor].tolist(),'intensity_relative_to_peak':float(intensity[competitor]/intensity[i])},'true_position_intensity_relative_to_peak':float(intensity[truth_idx]/intensity[i]),'leave_one_antenna_out':leave_out,'leave_out_shift_over_1cm_count':sum(r['shift_from_full_cm']>1 for r in leave_out),'max_leave_out_shift_cm':max(r['shift_from_full_cm'] for r in leave_out),'alternative_baseline':{'source_group':other,'candidate_cm':altpos.tolist(),'shift_cm':float(np.linalg.norm(altpos-peak))}}
        report['scans'][name]=row
        print(name,'error',round(row['error_cm'],2),'competitor',round(row['competitor_at_least_2cm_away']['intensity_relative_to_peak'],2),'leave-out >1cm',row['leave_out_shift_over_1cm_count'],'/16','max shift',round(row['max_leave_out_shift_cm'],2),'baseline shift',round(row['alternative_baseline']['shift_cm'],2),flush=True)
    folder = ROOT/'offline_review'
    folder.mkdir(exist_ok=True)
    (folder/'sensitivity_results.json').write_text(json.dumps(report,indent=2,allow_nan=False))
    # Preserve the exact inputs: later baseline overwrites cannot change this review.
    for group,path in files.items():
        (folder/f'baseline_{group}.json').write_bytes(path.read_bytes())
    for name in ['pair_delay_calibration.json','phase_stability_results.json']:
        (folder/name).write_bytes((ROOT/'data'/name).read_bytes())
    (folder/'geometry_reference.py').write_bytes((ROOT/'core/geometry.py').read_bytes())
    lines=['# Offline localization findings','', '**The current scans do not demonstrate reliable 1 cm localization. No rotation, calibration fit or channel tuning was applied.**','','## Results using the corresponding available baselines','','A uses its preserved baseline. B uses the current baseline that reproduces the saved B heatmaps; original acquisition provenance is not embedded in those scans. A height is corrected to 2.5 cm. B assumes the same support and cube height.','','| Scan | Candidate (cm) | Error (cm) | Competing peak / main peak, at least 2 cm away | Antenna omissions moving peak >1 cm |','|---|---|---:|---:|---:|']
    for name,row in report['scans'].items():
        lines.append(f"| {name} | {row['candidate_cm']} | {row['error_cm']:.2f} | {row['competitor_at_least_2cm_away']['intensity_relative_to_peak']:.2f} | {row['leave_out_shift_over_1cm_count']}/16 |")
    lines += ['','The omission results measure dependence on subsets of channels; they are not physical repeatability tests. A strong competitor means a small change in the measured data can potentially select a different peak.','','## What is supported','','- The reported hemisphere dimensions, arm positions and numbering match the current model.','- A single XY rotation does not explain all A/B results or their depth errors.','- Baseline subtraction leaves structured empty-control responses. A changed baseline can move reconstructed locations substantially.','- Phase stability of the averaged empty scans does not verify antenna phase response or per-pair target-path calibration.','- The current confidence flag is not a validated indicator of localization correctness.','- All seven saved target files passed finite-value, complete 101-point and frequency-grid checks; this cannot recover acquisition details discarded before saving.','','## What remains unknown','','The files cannot independently establish whether the remaining error is dominated by antenna phase response, multipath, incorrect system-delay offsets, or handling/time drift. Antenna-position confirmation is based on user measurements and labels, not a measured electromagnetic phase-center map.','','## One test for the next office visit','','Run `python capture_target_toggle.py` from the backend folder when the device is available. Enter the measured center, for example `2 2 2.5` for the same 1 cm cube on the 2 cm support. Keep the support, antennas and cables fixed. Follow the five stages: empty, cube present, empty, cube present, empty. Return the same cube to the same marked position and orientation. The script records three individual sweeps per stage and snapshots the reference files without overwriting the active baseline.','','Analyze each target stage against the empty stages before and after it; check whether a repeatable target-induced difference survives both reference choices before attempting a new calibration fit. No acquisition is required today.']
    (folder/'findings.md').write_text('\n'.join(lines)+'\n')
    print('Saved offline_review/findings.md and sensitivity_results.json')


if __name__=='__main__':
    main()
