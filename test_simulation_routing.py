import os
os.environ['NAIBRA_STORAGE']='sqlite'
os.environ['NAIBRA_DB_PATH']=':memory:'
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
import server

class SimulationRouting(unittest.TestCase):
    def test_explicit_transport_routing(self):
        with TestClient(server.app) as api:
            with patch.object(server, 'capture_real_hardware_sweep', return_value=None) as hardware:
                api.post('/api/bridge/connect', json={'transport':'simulated'})
                response=api.post('/api/scan/start', json={'true_position_cm':{'x':1,'y':2,'z':3}})
                self.assertEqual(response.status_code,200,response.text)
                scan=response.json()
                self.assertTrue(scan['simulated'])
                self.assertTrue(0 <= scan['metrics']['overall_score'] <= 100)
                self.assertTrue(0 <= scan['left']['score'] <= 100)
                self.assertIn('c', scan['left']['dots'][0])
                self.assertIn('s', scan['left']['dots'][0])
                self.assertTrue(scan['left']['dots'])
                self.assertEqual(scan['left']['dots'][0]['source'],'simulated')
                self.assertIsNone(scan['hardware_capture'])
                self.assertEqual(scan['true_position_cm']['z'],3)
                hardware.assert_not_called()
                for transport in ['wired','bluetooth']:
                    api.put('/api/config',json={'transport':transport})
                    self.assertEqual(api.post('/api/scan/start',json={}).status_code,503)
                self.assertEqual(hardware.call_count,2)
                self.assertEqual(len(api.get('/api/scans').json()),1)

if __name__=='__main__': unittest.main()

