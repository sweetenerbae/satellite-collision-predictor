import asyncio
import json
import math
import sqlite3
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from conjunction import ConjunctionEvent
from satellite import Satellite
from services.snapshot_store import SnapshotStore, ScreeningSnapshot, event_id
from services.screening_service import ScreeningService, screening_service
from services.catalog_service import catalog
from services.ephemeris_service import build_ephemeris
from test_api import request


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.store = SnapshotStore(Path(self.directory.name)/"nested/snapshots.sqlite3")
        self.store.initialize()
        data = json.loads((Path(__file__).parent/"fixtures/station.json").read_text())
        self.sat = Satellite(data)
        self.other = Satellite(dict(data, NORAD_CAT_ID=50000, OBJECT_NAME="Synthetic neighbour",
                                    MEAN_ANOMALY=data["MEAN_ANOMALY"]+.1))
        self.time = datetime.fromisoformat(data["EPOCH"]).replace(tzinfo=timezone.utc)
        self.events = tuple(ConjunctionEvent(self.sat, self.other, 11+i, 1.2,
                                             self.time+timedelta(minutes=i)) for i in range(3))
        self.first = ScreeningSnapshot(str(uuid4()), self.time, self.time,
            self.time+timedelta(hours=24), 2, {"algorithm":"test"}, self.events)
        screening_service.__init__()
        self.addCleanup(screening_service.__init__)

    def get(self, path, query=None):
        return asyncio.run(request(path, query))

    def test_round_trip_original_elements_and_state(self):
        self.store.save(self.first)
        restored = SnapshotStore(self.store.path).latest()
        self.assertEqual(restored.id, self.first.id)
        self.assertEqual([event_id(e) for e in restored.events], [event_id(e) for e in self.events])
        self.assertEqual(restored.events[0].sat1.omm_data, self.sat.omm_data)
        before = build_ephemeris(self.sat, self.time, self.time+timedelta(seconds=60))
        after = build_ephemeris(restored.events[0].sat1, self.time, self.time+timedelta(seconds=60))
        self.assertEqual(before.samples, after.samples)
        # The exposed source is a copy, not mutable backing state.
        elements = self.sat.omm_data
        elements["MEAN_ANOMALY"] += 20
        self.assertNotEqual(elements, self.sat.omm_data)

    def test_restart_and_original_calculation_time(self):
        self.store.save(self.first)
        service = ScreeningService()
        service.configure_store(SnapshotStore(self.store.path))
        self.assertEqual(service.status()["snapshot_id"], self.first.id)
        self.assertEqual(service.get_last_updated_at(), self.time)
        self.assertEqual(service.status()["is_stale"], self.first.window_end < datetime.now(timezone.utc))
        self.assertEqual(service.status()["state"], "ready")

    def test_empty_success_is_durable(self):
        empty = replace(self.first, events=())
        self.store.save(empty)
        screening_service.configure_store(self.store)
        self.assertEqual(self.get("/conjunctions"), (200, []))
        page = self.get("/conjunctions/page")[1]
        self.assertEqual(page["total"], 0)
        self.assertIsNone(page["next_offset"])
        self.assertEqual(page["snapshot_id"], empty.id)

    def test_page_stays_pinned_across_new_calculation_and_restart(self):
        self.store.save(self.first)
        screening_service.configure_store(self.store)
        code, page = self.get("/conjunctions/page", {"limit":1})
        self.assertEqual(code, 200)
        self.assertEqual(page["next_offset"], 1)
        newer = replace(self.first, id=str(uuid4()), computed_at=self.time+timedelta(hours=1),
                        events=(replace(self.events[0], tca=self.time+timedelta(hours=2)),))
        self.store.save(newer)
        screening_service.configure_store(SnapshotStore(self.store.path))
        second_page = self.get("/conjunctions/page",
            {"snapshot_id":page["snapshot_id"],"offset":page["next_offset"],"limit":1})[1]
        self.assertEqual(second_page["snapshot_id"], self.first.id)
        self.assertEqual(second_page["total"], 3)
        self.assertEqual(second_page["items"][0]["id"], event_id(self.events[1]))
        self.assertEqual(self.get("/conjunctions/page")[1]["snapshot_id"], newer.id)
        self.assertEqual(self.get("/conjunctions", {"snapshot_id":self.first.id})[1][0]["snapshot_id"],self.first.id)

    def test_archived_event_and_trajectory_ignore_current_catalog(self):
        self.store.save(self.first)
        newer = replace(self.first,id=str(uuid4()),events=())
        self.store.save(newer)
        screening_service.configure_store(self.store)
        id = event_id(self.events[0])
        with patch.object(catalog,"get_by_id",return_value=None):
            code, detail = self.get("/conjunctions/"+id)
            self.assertEqual(code,200)
            self.assertEqual(detail["snapshot_id"],self.first.id)
            code, pair = self.get("/conjunctions/"+id+"/ephemeris")
            self.assertEqual(code,200)
            self.assertEqual(pair["snapshot_id"],self.first.id)
            self.assertEqual(pair["satellite_1"]["element_epoch"],self.sat.epoch)
        code,_ = self.get("/conjunctions/"+id,{"snapshot_id":newer.id})
        self.assertEqual(code,404)  # Explicit pin never falls back to another run.

    def test_repeated_event_id_resolves_latest_or_explicit_snapshot(self):
        self.store.save(self.first)
        newer = replace(self.first,id=str(uuid4()),computed_at=self.time+timedelta(hours=1),
                        events=(replace(self.events[0],distance_km=15),))
        self.store.save(newer)
        screening_service.configure_store(self.store)
        id = event_id(self.events[0])
        self.assertEqual(self.get("/conjunctions/"+id)[1]["miss_distance_km"],15)
        self.assertEqual(self.get("/conjunctions/"+id,{"snapshot_id":self.first.id})[1]["miss_distance_km"],11)

    def test_transaction_rolls_back_partial_insert(self):
        self.store.save(self.first)
        bad = replace(self.first,id=str(uuid4()),events=(self.events[0],self.events[0]))
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.save(bad)
        self.assertIsNone(self.store.get(bad.id))
        self.assertEqual(self.store.latest().id,self.first.id)

    def test_snapshot_id_cannot_be_overwritten(self):
        self.store.save(self.first)
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.save(replace(self.first,events=()))
        self.assertEqual(len(self.store.get(self.first.id).events),3)

    def test_write_failure_keeps_published_snapshot(self):
        self.store.save(self.first)
        service = ScreeningService()
        service.configure_store(self.store)
        with patch.object(catalog,"get_all",return_value=[self.sat,self.other]),              patch("services.screening_service.find_conjunctions",return_value=list(self.events)),              patch.object(self.store,"save",side_effect=sqlite3.OperationalError("disk full")):
            with self.assertRaises(sqlite3.OperationalError):
                service.run_screening()
        self.assertEqual(service.current_snapshot().id,self.first.id)
        self.assertEqual(self.store.latest().id,self.first.id)
        self.assertEqual(service.status()["state"],"failed")

    def test_success_is_durable_before_publish(self):
        self.store.save(self.first)
        service=ScreeningService()
        service.configure_store(self.store)
        real_save=self.store.save
        def observe_save(snapshot):
            self.assertEqual(service.current_snapshot().id,self.first.id)
            real_save(snapshot)
            self.assertEqual(self.store.latest().id,snapshot.id)
        with patch.object(catalog,"get_all",return_value=[self.sat,self.other]),              patch("services.screening_service.find_conjunctions",return_value=list(self.events)),              patch.object(self.store,"save",side_effect=observe_save):
            service.run_screening()
        self.assertNotEqual(service.current_snapshot().id,self.first.id)
        self.assertEqual(service.current_snapshot().id,self.store.latest().id)

    def test_paging_validation_unknown_snapshot_and_pending(self):
        self.assertEqual(self.get("/conjunctions/page")[0],503)
        self.assertEqual(self.get("/conjunctions/page",{"snapshot_id":str(uuid4())})[0],404)
        self.store.save(self.first)
        screening_service.configure_store(self.store)
        for query in [{"snapshot_id":"not-a-uuid"},{"limit":501},{"offset":-1}]:
            self.assertEqual(self.get("/conjunctions/page",query)[0],422)
        last=self.get("/conjunctions/page",{"offset":2,"limit":1})[1]
        self.assertIsNone(last["next_offset"])
        self.assertEqual(self.get("/conjunctions/page",{"offset":20})[1]["items"],[])

    def test_lifespan_restores_before_background_refresh(self):
        from main import app, lifespan
        self.store.save(self.first)
        async def background():
            await asyncio.Event().wait()
        async def check():
            with patch.dict("os.environ",{"SATELLITE_DB_PATH":str(self.store.path)}),                  patch("main.update_loop",new=background):
                async with lifespan(app):
                    self.assertEqual(screening_service.current_snapshot().id,self.first.id)
        asyncio.run(check())

    def test_future_database_version_is_not_modified(self):
        with self.store.connection() as conn:
            conn.execute("PRAGMA user_version=99")
        with self.assertRaises(ValueError):
            self.store.initialize()
        with self.store.connection() as conn:
            self.assertEqual(conn.execute("PRAGMA user_version").fetchone()[0],99)
