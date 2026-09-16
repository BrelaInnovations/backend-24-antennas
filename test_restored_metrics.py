import os,json,asyncio
os.environ['NAIBRA_STORAGE']='sqlite'
os.environ['NAIBRA_DB_PATH']=':memory:'
import server
from fastapi.testclient import TestClient
with TestClient(server.app) as api:
    first=api.post('/api/scan/start',json={}).json()
    second=api.post('/api/scan/start',json={}).json()
    assert second['metrics']['past_vs_current']['prev_scan_id']==first['id']
    comparison=api.get('/api/compare/'+first['id']+'/'+second['id']).json()
    assert comparison['deltas']['overall']==second['metrics']['overall_score']-first['metrics']['overall_score']
    with open('report_test_fixture.json','w',encoding='utf-8') as f: json.dump(second,f)
print('PASS: saved simulation comparison and previous-scan metrics restored.')
