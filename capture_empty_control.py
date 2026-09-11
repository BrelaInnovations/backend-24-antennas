"""Save three empty controls and their baseline; do not replace calibration or manifest.

Remove the cube but leave its support, antennas and cables fixed.
Run from the backend folder: python capture_empty_control.py
"""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def main():
    root = Path(__file__).resolve().parent
    if Path.cwd().resolve() != root:
        raise RuntimeError(f'Run this script from {root}')
    baseline_bytes = (root/'data/baseline_full_sweep.json').read_bytes()
    print('Remove the cube. Keep the rubber support, antennas and cables fixed.')
    input('Press Enter when ready, or Ctrl+C to cancel: ')
    # Import only after confirmation: capture_one_sweep opens hardware when called.
    from capture_labeled_scan import capture_one_sweep
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    folder = root/'dataset'/f'empty_control_{stamp}'
    folder.mkdir(parents=True, exist_ok=False)
    (folder/'baseline_reference.json').write_bytes(baseline_bytes)
    metadata = {'purpose':'Cube removed; support unchanged', 'baseline_sha256':hashlib.sha256(baseline_bytes).hexdigest(), 'scans':[], 'complete':False}
    for filename in ['pair_delay_calibration.json','phase_stability_results.json']:
        (folder/filename).write_bytes((root/'data'/filename).read_bytes())
    (folder/'geometry_reference.py').write_bytes((root/'core/geometry.py').read_bytes())
    def save_metadata():
        (folder/'metadata.json').write_text(json.dumps(metadata,indent=2))
    save_metadata()
    for i in range(1,4):
        sweep = capture_one_sweep()
        name = f'empty_{i}.json'
        (folder/name).write_text(json.dumps(sweep,allow_nan=False))
        metadata['scans'].append(name)
        save_metadata()
        print(f'Saved empty control {i}/3')
    metadata['complete'] = True
    save_metadata()
    print(f'Finished. Saved controls and baseline reference in {folder}')
    print('The active baseline, calibration and target manifest were not changed.')


if __name__ == '__main__':
    main()
