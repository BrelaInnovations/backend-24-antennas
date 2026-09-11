"""Guided empty/target/empty/target/empty test. Saves individual sweeps.

Run in the backend folder: python capture_target_toggle.py
Keep rubber support fixed and use one cube at the same measured position.
Never overwrites the active baseline, calibration or target manifest.
"""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import math


def validate_sweep(sweep):
    """Reject missing channels, bins or invalid complex values before saving."""
    expected = {f'TX{tx}-RX{rx}' for tx in range(1,13) for rx in range(1,13)}
    if set(sweep) != expected:
        raise ValueError('Sweep does not contain exactly all 144 TX/RX pairs')
    for label, trace in sweep.items():
        freqs, real, imag = [trace.get(k,[]) for k in ('freqs','s21_real','s21_imag')]
        if trace.get('error') or any(len(a) != 101 for a in (freqs,real,imag)):
            raise ValueError(f'{label}: incomplete 101-point sweep')
        if not all(math.isfinite(v) for a in (freqs,real,imag) for v in a):
            raise ValueError(f'{label}: nonfinite spectrum')
        if any(abs(f-(2+0.04*i)) > 1e-8 for i,f in enumerate(freqs)):
            raise ValueError(f'{label}: incorrect 2-6 GHz frequency grid')


def main():
    root = Path(__file__).resolve().parent
    if Path.cwd().resolve() != root:
        raise RuntimeError(f'Run from {root}')
    print('Keep antennas, cables and rubber support fixed throughout.')
    print('Use ONE cube. Mark its position so both placements are the same.')
    xyz = [float(x) for x in input('Cube CENTER x y z in cm (example: 2 2 2.5): ').split()]
    if len(xyz) != 3 or not all(math.isfinite(x) for x in xyz) or xyz[2] < 0 or sum(x*x for x in xyz) > 64:
        raise ValueError('Enter three finite coordinates inside the 8 cm hemisphere.')
    from capture_labeled_scan import capture_one_sweep
    import capture_labeled_scan as capture
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    folder = root/'dataset'/f'target_toggle_{stamp}'
    folder.mkdir(parents=True, exist_ok=False)
    meta = {'target_center_cm':xyz, 'purpose':'Repeated target insertion with bracketing empty controls', 'individual_sweeps_per_stage':3,'stages':[],'complete':False,'snapshot_sha256':{}}
    for relative in ['data/baseline_full_sweep.json','data/pair_delay_calibration.json','data/phase_stability_results.json','core/geometry.py','2-6_cal_with_new_cable.cal']:
        content = (root/relative).read_bytes()
        (folder/Path(relative).name).write_bytes(content)
        meta['snapshot_sha256'][relative] = hashlib.sha256(content).hexdigest()
    def save():
        (folder/'metadata.json').write_text(json.dumps(meta,indent=2,allow_nan=False))
    save()
    previous = capture.NUM_SWEEP_AVERAGES
    capture.NUM_SWEEP_AVERAGES = 1
    try:
        for i,state in enumerate(['empty','target','empty','target','empty'],1):
            instruction = 'REMOVE the cube; leave its support fixed' if state == 'empty' else f'PLACE one cube with its center at {xyz} cm'
            print(f'\nStage {i}/5: {instruction}.')
            input('Move your hands away, then press Enter to capture: ')
            stage = {'stage':i,'state':state,'scans':[]}
            meta['stages'].append(stage)
            save()
            for repeat in range(1,4):
                started = datetime.now(timezone.utc).isoformat()
                sweep = capture_one_sweep()
                validate_sweep(sweep)
                name = f'{i}_{state}_{repeat}.json'
                (folder/name).write_text(json.dumps(sweep,allow_nan=False))
                stage['scans'].append({'file':name,'started_utc':started,'finished_utc':datetime.now(timezone.utc).isoformat()})
                save()
                print(f'Stage {i}/5: individual sweep {repeat}/3 saved.')
        meta['complete'] = True
        save()
    finally:
        capture.NUM_SWEEP_AVERAGES = previous
        print(f'Results saved in {folder}')
    print('Finished. No baseline or calibration was changed. Tell me done.')


if __name__ == '__main__':
    main()
