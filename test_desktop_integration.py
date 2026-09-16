"""Integration check: actual FastAPI routes and persistent SQLite, mocked scanner."""
import os
import tempfile
import unittest
from unittest.mock import patch

os.environ['NAIBRA_STORAGE'] = 'sqlite'
os.environ['NAIBRA_DB_PATH'] = ':memory:'
from fastapi.testclient import TestClient
import server
from local_database import LocalDatabase


class DesktopIntegration(unittest.TestCase):
    def test_routes_and_persistence(self):
        with tempfile.TemporaryDirectory() as folder:
            database = LocalDatabase(folder + '/test.sqlite3')
            with patch.object(server, 'db', database), patch.object(server, 'client', database):
                with TestClient(server.app) as api:
                    for route in ['/', '/config', '/antenna/layout', '/user', '/periods', '/cycle/status', '/avatar/status', '/scans']:
                        self.assertEqual(api.get('/api' + route).status_code, 200, route)
                    self.assertEqual(api.put('/api/user', json={'name': 'Desktop test'}).status_code, 200)
                    period = api.post('/api/periods', json={'start_date': '2026-09-01'}).json()
                    self.assertEqual(api.post('/api/periods', json={'start_date': '2026-09-01'}).status_code, 409)
                    self.assertTrue(api.get('/api/cycle/status').json()['has_data'])
                    self.assertEqual(api.delete('/api/periods/' + period['id']).status_code, 200)
                    api.put('/api/config', json={'transport': 'wired'})
                    with patch.object(server, 'capture_real_hardware_sweep', return_value=None):
                        self.assertEqual(api.post('/api/scan/start', json={}).status_code, 503)
                    capture = {'dmas_snr': {'confident': True}, 'dmas_full_results': [{'x': 1, 'y': 2, 'z': 3, 'intensity': 8}]}
                    with patch.object(server, 'capture_real_hardware_sweep', return_value=capture):
                        for point in [{'x': 1, 'y': 2}, {'x': 0, 'y': 0, 'z': -1}, {'x': 9, 'y': 0, 'z': 0}]:
                            self.assertEqual(api.post('/api/scan/start', json={'true_position_cm': point}).status_code, 422)
                        response = api.post('/api/scan/start', json={'label': 'Integration', 'true_position_cm': {'x': 1, 'y': 2, 'z': 2}})
                        self.assertEqual(response.status_code, 200, response.text)
                        scan = response.json()
                        self.assertEqual(scan['true_position_cm'], {'x': 1, 'y': 2, 'z': 2})
                        self.assertEqual(scan['true_position_normalized'], {'x': 0.125, 'y': 0.25, 'z': 0.25})
                        self.assertEqual(scan['localization_error_cm'], 1.0)
                    self.assertEqual(api.get('/api/scans/latest').json()['true_position_cm'], scan['true_position_cm'])
                    self.assertEqual(len(api.get('/api/scans').json()), 1)
                    self.assertEqual(api.get('/api/compare/' + scan['id'] + '/' + scan['id']).status_code, 200)
                    self.assertEqual(api.get('/api/avatar/status').json()['total_scans'], 1)
                    self.assertEqual(api.delete('/api/scans/' + scan['id']).status_code, 200)
                    self.assertEqual(api.get('/api/scans/latest').status_code, 404)
                    self.assertEqual(api.options('/api/config', headers={'Origin': 'http://localhost:8081', 'Access-Control-Request-Method': 'GET'}).status_code, 200)
            reopened = LocalDatabase(folder + '/test.sqlite3')
            import asyncio
            self.assertEqual(asyncio.run(reopened.users.find_one({'id': 'main'}))['name'], 'Desktop test')
            reopened.close()


if __name__ == '__main__':
    unittest.main()
