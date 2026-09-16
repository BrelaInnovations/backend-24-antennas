import ast
import asyncio
import math
import unittest
from pathlib import Path
from types import SimpleNamespace
from dmas_localization import localization_result, localization_metrics, localization_antennas


class LocalizationTests(unittest.TestCase):
    def test_thermal_bands_preserve_coordinates_and_raw_intensity(self):
        result = localization_result([
            dict(x=-2, y=4, z=6, intensity=5),
            dict(x=0, y=0, z=1, intensity=2),
            dict(x=4, y=-2, z=3, intensity=10),
        ], True)
        self.assertEqual(result['dot_count'], 3)
        self.assertEqual(result['dots'][0]['x'], 0.5)
        self.assertEqual(result['dots'][0]['y'], -0.25)
        self.assertEqual(result['dots'][0]['z'], 0.375)
        self.assertEqual(result['dots'][0]['intensity'], 10)
        self.assertEqual(result['dots'][0]['s'], 1.0)
        self.assertEqual([d['c'] for d in result['dots']], ['high', 'medium', 'low'])
        self.assertIsNone(result['score'])

    def test_thermal_cloud_low_tail_and_clear_space(self):
        values = [100, 75, 45, 20, 5, 4.99, 0]
        result = localization_result([dict(x=i/10, y=0, z=1, intensity=v) for i,v in enumerate(values)], True)
        self.assertEqual([d['c'] for d in result['dots']], ['high', 'high', 'medium', 'low', 'baseline'])
        self.assertEqual(result['dot_counts'], dict(high=2, medium=1, low=1, baseline=1))
        self.assertEqual(result['dots'][-1]['intensity'], 5)
        self.assertEqual(result['color_mode'], 'relative_intensity')
        self.assertIsNone(result['score'])
        # No synthetic surrounding positions are added.
        self.assertEqual([round(d['x']*8, 2) for d in result['dots']], [0, .1, .2, .3, .4])

    def test_low_confidence_is_not_healthy(self):
        result = localization_result([dict(x=1, y=2, z=3, intensity=5)], False)
        self.assertEqual(len(result['dots']), 1)
        self.assertEqual(result['dots'][0]['c'], 'high')
        self.assertTrue(result['display_notice'])
        self.assertFalse(result['confident'])
        self.assertEqual(result['status'], 'inconclusive')
        self.assertIsNone(result['peak_location_cm'])
        metrics = localization_metrics(result, result)
        self.assertEqual(metrics['verdict'], 'inconclusive')
        self.assertIsNone(metrics['overall_score'])

    def test_invalid_empty_and_nonpositive_field(self):
        result = localization_result([{}, dict(x=math.nan, y=0, z=0, intensity=8),
                                      dict(x=0, y=0, z=0, intensity=0)], True)
        self.assertEqual(result['status'], 'unavailable')
        self.assertEqual(result['dots'], [])
        for kwargs in ({'dome_radius_cm': 0}, {'threshold_fraction': 0}, {'max_dots': 0}):
            with self.assertRaises(ValueError):
                localization_result([], True, **kwargs)

    def test_bounded_deterministic_markers_are_actual_voxels(self):
        voxels = [dict(x=i/1000, y=0, z=1, intensity=1) for i in range(5000)]
        result = localization_result(voxels, True, max_dots=20)
        self.assertEqual(result['dot_count'], 20)
        self.assertEqual(result['selected_voxel_count'], 5000)
        self.assertTrue(result['sampled'])
        self.assertEqual(result['dots'], localization_result(list(reversed(voxels)), True, max_dots=20)['dots'])
        self.assertEqual(result['dots'][-1]['x'] * 8, 4.75)


# Execute the actual route bodies with in-memory infrastructure: no serial
# capture, Mongo connection, or physical device side effects during tests.
class RouteTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        module = ast.parse(Path('server.py').read_text(encoding='utf-8'))
        names = {'start_scan', 'compute_metrics', 'scan_summary', 'recompute_threshold', 'compare_scans'}
        bodies = [n for n in module.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in names]
        for n in bodies:
            n.decorator_list = []
        self.saved = []
        self.capture = {'dmas_full_results': [dict(x=2, y=-2, z=4, intensity=5)],
                        'dmas_snr': {'confident': True}, 'weights': [1]}
        async def find_one(*args, **kwargs):
            return self.saved[-1] if self.saved else None
        async def insert_one(doc):
            self.saved.append(doc)
        async def config():
            return dict(num_prongs=4, antennas_per_prong=4, freq_start_mhz=2000,
                        freq_stop_mhz=6000, sweep_points=51, connection_mode='live')
        async def threadpool(fn, *args):
            return fn(*args)
        class HTTPException(Exception):
            def __init__(self, status_code, detail):
                self.status_code = status_code
                self.detail = detail
        from datetime import datetime, timezone
        import random
        import uuid
        self.env = dict(ScanStart=object, ThresholdRecompute=object, Optional=__import__('typing').Optional,
                        db=SimpleNamespace(scans=SimpleNamespace(find_one=find_one, insert_one=insert_one)),
                        get_config_doc=config, random=random, uuid=uuid, datetime=datetime, timezone=timezone,
                        now_iso=lambda: '2026-09-09T00:00:00Z', scan_lock=asyncio.Lock(),
                        run_in_threadpool=threadpool, capture_real_hardware_sweep=lambda cfg: self.capture,
                        localization_result=localization_result, localization_metrics=localization_metrics,
                        localization_antennas=localization_antennas,
                        antenna_positions=lambda cfg: [], run_antenna_check=lambda *args: [],
                        HTTPException=HTTPException)
        exec(compile(ast.Module(body=bodies, type_ignores=[]), 'server.py', 'exec'), self.env)

    async def test_scan_persists_only_localization_and_compact_summary(self):
        result = await self.env['start_scan'](SimpleNamespace(label='test'))
        self.assertEqual(result['algorithm'], 'dmas-cf')
        self.assertEqual(result['left']['dots'], result['right']['dots'])
        self.assertNotIn('dmas_full_results', result['hardware_capture'])
        self.assertEqual(self.env['scan_summary'](result)['left_dot_count'], 1)
        self.assertIsNone(result['metrics']['overall_score'])
        comparison = await self.env['compare_scans']('a', 'b')
        self.assertEqual(comparison['deltas'], {})

    async def test_failed_reconstruction_cannot_fall_back_to_weights(self):
        self.capture = {'weights': [1], 'dmas_full_results': []}
        result = await self.env['start_scan'](SimpleNamespace(label='test'))
        self.assertEqual(result['left']['dots'], [])
        self.assertEqual(result['left']['status'], 'unavailable')

    async def test_no_capture_cannot_fall_back_to_simulation(self):
        self.capture = None
        with self.assertRaises(self.env['HTTPException']) as cm:
            await self.env['start_scan'](SimpleNamespace(label='test'))
        self.assertEqual(cm.exception.status_code, 503)
        self.assertEqual(self.saved, [])

    async def test_legacy_recompute_is_retired(self):
        with self.assertRaises(self.env['HTTPException']) as cm:
            await self.env['recompute_threshold']('id', SimpleNamespace(sensitivity_db=3))
        self.assertEqual(cm.exception.status_code, 410)

    async def test_busy_capture_rejected(self):
        async with self.env['scan_lock']:
            with self.assertRaises(self.env['HTTPException']) as cm:
                await self.env['start_scan'](SimpleNamespace(label='test'))
        self.assertEqual(cm.exception.status_code, 409)


if __name__ == '__main__':
    unittest.main()
