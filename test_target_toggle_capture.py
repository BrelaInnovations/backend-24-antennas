"""Hardware-free validation and workflow regression tests for the toggle test."""
import copy
import json
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import capture_target_toggle as toggle


def valid_sweep():
    return {f'TX{tx}-RX{rx}':{'freqs':[2+0.04*i for i in range(101)],'s21_real':[0.1]*101,'s21_imag':[0.02]*101} for tx in range(1,9) for rx in range(1,9)}


class ToggleCaptureTests(unittest.TestCase):
    def test_valid(self):
        toggle.validate_sweep(valid_sweep())

    def test_bad_data_rejected(self):
        for fault in ['pair','bin','nan','frequency','error']:
            with self.subTest(fault=fault):
                scan=valid_sweep();trace=scan['TX1-RX1']
                if fault=='pair':del scan['TX1-RX1']
                elif fault=='bin':trace['s21_real'].pop()
                elif fault=='nan':trace['s21_imag'][0]=float('nan')
                elif fault=='frequency':trace['freqs'][20]=3.1
                else:trace['error']='read failed'
                with self.assertRaises(ValueError):toggle.validate_sweep(scan)

    def run_fake(self, fail=False):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            paths=['data/baseline_full_sweep.json','data/pair_delay_calibration.json','data/phase_stability_results.json','core/geometry.py','2-6_cal_with_new_cable.cal']
            for p in paths:
                file=root/p;file.parent.mkdir(parents=True,exist_ok=True);file.write_text('reference bytes')
            fake=types.ModuleType('capture_labeled_scan');fake.NUM_SWEEP_AVERAGES=3
            calls=[]
            def capture():
                calls.append(fake.NUM_SWEEP_AVERAGES)
                return {} if fail else valid_sweep()
            fake.capture_one_sweep=capture
            with patch.object(toggle,'__file__',str(root/'capture_target_toggle.py')),patch.object(Path,'cwd',return_value=root),patch.dict('sys.modules',{'capture_labeled_scan':fake}),patch('builtins.input',side_effect=['2 2 2.5','','','','','']),patch('builtins.print'):
                if fail:
                    with self.assertRaises(ValueError):toggle.main()
                else:toggle.main()
            folder=next((root/'dataset').glob('target_toggle_*'))
            meta=json.loads((folder/'metadata.json').read_text())
            self.assertEqual(fake.NUM_SWEEP_AVERAGES,3)
            self.assertTrue(all(x==1 for x in calls))
            self.assertEqual(meta['complete'],not fail)
            self.assertEqual(len(calls),1 if fail else 15)
            self.assertEqual(sum(len(s['scans']) for s in meta['stages']),0 if fail else 15)
            if not fail:self.assertEqual([s['state'] for s in meta['stages']],['empty','target','empty','target','empty'])
            for p in paths:self.assertEqual((root/p).read_text(),'reference bytes')

    def test_complete_workflow_preserves_references(self):
        self.run_fake()

    def test_failed_capture_remains_incomplete(self):
        self.run_fake(fail=True)


if __name__=='__main__':unittest.main()
