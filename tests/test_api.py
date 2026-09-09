import asyncio
import json
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlencode
from main import app
from services.catalog_service import catalog
from services.screening_service import screening_service
from services.ephemeris_service import build_ephemeris
from predictor import candidate_pairs_at_time
from schemas.conjunction import ConjunctionResponse
from conjunction import ConjunctionEvent


async def request(path, query=None):
    messages = []
    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}
    async def send(message):
        messages.append(message)
    scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
             "method": "GET", "scheme": "http", "path": path, "raw_path": path.encode(),
             "query_string": urlencode(query or {}).encode(), "root_path": "", "headers": [],
             "client": ("127.0.0.1", 1000), "server": ("localhost", 8000)}
    await app(scope, receive, send)
    status = next(item["status"] for item in messages if item["type"] == "http.response.start")
    body = b"".join(item.get("body", b"") for item in messages if item["type"] == "http.response.body")
    return status, json.loads(body)


class APITests(unittest.TestCase):
    def setUp(self):
        fixture = json.loads((Path(__file__).parent / "fixtures/station.json").read_text())
        with patch("services.catalog_service.fetch_satellites", return_value=[fixture]):
            catalog.load()
        screening_service.__init__()
        self.satellite = catalog.get_all()[0]
        self.start = datetime.fromisoformat(fixture["EPOCH"]).replace(tzinfo=timezone.utc)

    def get(self, path, query=None):
        return asyncio.run(request(path, query))

    def test_health_and_pending_are_not_no_events(self):
        code, body = self.get('/health')
        self.assertEqual(code, 200)
        self.assertTrue(body['catalog']['ready'])
        self.assertEqual(body['catalog']['group'], 'STATIONS')
        self.assertEqual(self.get('/conjunctions')[0], 503)
        self.assertEqual(self.get('/conjunctions/status')[1]['state'], 'pending')

    def test_search_detail_and_limits(self):
        code, body = self.get('/satellites', {'query': str(self.satellite.norad_id)})
        self.assertEqual(code, 200)
        self.assertEqual(len(body), 1)
        self.assertEqual(self.get('/satellites', {'query': 'unknown'})[1], [])
        self.assertEqual(self.get('/satellites', {'limit': 501})[0], 422)
        self.assertEqual(self.get('/satellites/999999999')[0], 404)
        detail = self.get(f'/satellites/{self.satellite.norad_id}')[1]
        self.assertEqual(detail['epoch'], self.satellite.epoch)

    def test_ephemeris_contract_and_inclusive_end(self):
        end = self.start + timedelta(seconds=125)
        query = {'start': self.start.isoformat(), 'end': end.isoformat(), 'step_seconds': 60}
        code, body = self.get(f'/satellites/{self.satellite.norad_id}/ephemeris', query)
        self.assertEqual(code, 200)
        self.assertEqual(body['frame'], 'TEME')
        self.assertEqual(body['time_scale'], 'UTC')
        self.assertEqual(len(body['samples']), 4)
        self.assertEqual(datetime.fromisoformat(body['samples'][-1]['time'].replace('Z','+00:00')), end)
        self.assertEqual(len(body['samples'][0]['position_km']), 3)
        self.assertGreater(sum(v*v for v in body['samples'][0]['position_km'])**0.5, 6000)

    def test_ephemeris_rejects_naive_oversized_reversed(self):
        path = f'/satellites/{self.satellite.norad_id}/ephemeris'
        for query in [
            {'start':'2026-09-08T00:00:00','end':'2026-09-08T01:00:00Z'},
            {'start':self.start.isoformat(),'end':self.start.isoformat()},
            {'start':self.start.isoformat(),'end':(self.start+timedelta(hours=7)).isoformat()},
            {'start':self.start.isoformat(),'end':(self.start+timedelta(hours=1)).isoformat(),'step_seconds':1},
        ]:
            self.assertEqual(self.get(path,query)[0],422)

    def test_sgp4_error_is_explicit(self):
        with patch.object(self.satellite,'state_at',side_effect=RuntimeError('SGP4 error')):
            code,_=self.get(f'/satellites/{self.satellite.norad_id}/ephemeris',
                {'start':self.start.isoformat(),'end':(self.start+timedelta(minutes=1)).isoformat()})
        self.assertEqual(code,503)

    def test_successful_empty_snapshot_and_failed_refresh(self):
        with patch('services.screening_service.find_conjunctions',return_value=[]):
            screening_service.run_screening(hours=1)
        updated=screening_service.get_last_updated_at()
        parameters=screening_service.status()['parameters']
        self.assertEqual(parameters['algorithm'],'sampled-local-minima-v2')
        self.assertEqual(self.get('/conjunctions'),(200,[]))
        with patch('services.screening_service.find_conjunctions',side_effect=RuntimeError('fail')):
            with self.assertRaises(RuntimeError):screening_service.run_screening(hours=1)
        self.assertEqual(screening_service.get_last_updated_at(),updated)
        self.assertEqual(screening_service.status()['state'],'failed')
        self.assertEqual(screening_service.status()['parameters'],parameters)
        self.assertFalse(screening_service.is_running())

    def test_event_id_and_detail_match_list(self):
        other=type('Other',(),{'norad_id':900002,'name':'Example'})()
        event=ConjunctionEvent(self.satellite,other,11.09,12.4,self.start)
        with patch('services.screening_service.find_conjunctions',return_value=[event]):
            screening_service.run_screening(hours=1)
        data=self.get('/conjunctions')[1][0]
        self.assertEqual(self.get('/conjunctions/'+data['id']),(200,data))
        self.assertNotIn('collision_probability',data)
        self.assertEqual(data['tca_location'],'interior')
        self.assertEqual(self.get('/conjunctions/unknown')[0],404)

    def test_event_trajectories_keep_screened_elements(self):
        event = ConjunctionEvent(self.satellite, self.satellite, 0.0, 0.0, self.start)
        with patch('services.screening_service.find_conjunctions', return_value=[event]):
            screening_service.run_screening(hours=1)
        id = self.get('/conjunctions')[1][0]['id']
        with patch.object(catalog, 'get_by_id', return_value=None):
            code, body = self.get('/conjunctions/'+id+'/ephemeris',
                                  {'seconds_before':31, 'seconds_after':30, 'step_seconds':10})
        self.assertEqual(code, 200)
        self.assertEqual(body['satellite_1']['element_epoch'], self.satellite.epoch)
        self.assertEqual(len(body['satellite_1']['samples']), 9)
        self.assertIn(self.start, [datetime.fromisoformat(s['time'].replace('Z','+00:00')) for s in body['satellite_1']['samples']])
        self.assertEqual([s['time'] for s in body['satellite_1']['samples']],
                         [s['time'] for s in body['satellite_2']['samples']])
        self.assertEqual(self.get('/conjunctions/unknown/ephemeris')[0], 404)

    def test_boundary_event_contract(self):
        event = ConjunctionEvent(self.satellite, self.satellite, .5, 0., self.start,
                                 tca_location="window_start")
        with patch('services.screening_service.find_conjunctions', return_value=[event]):
            screening_service.run_screening(hours=1)
        code, events = self.get('/conjunctions')
        self.assertEqual(code, 200)
        self.assertEqual(events[0]['tca_location'], 'window_start')
        code, status = self.get('/conjunctions/status')
        self.assertEqual(status['parameters']['refinement_step_seconds'], 10)

    def test_bad_catalog_keeps_previous_snapshot(self):
        with patch('services.catalog_service.fetch_satellites',return_value=[]):
            with self.assertRaises(ValueError):catalog.load()
        self.assertEqual(len(catalog.get_all()),1)
        self.assertEqual(catalog.status()['last_error'],'ValueError')

    def test_small_catalog_and_shared_fixture(self):
        self.assertEqual(candidate_pairs_at_time([],0,0,50),set())
        self.assertEqual(candidate_pairs_at_time([self.satellite],0,0,50),set())
        fixture=Path(__file__).parent.parent/'contracts/conjunction.example.json'
        self.assertEqual(ConjunctionResponse.model_validate_json(fixture.read_text()).miss_distance_km,11.09)

if __name__ == '__main__':
    unittest.main()
