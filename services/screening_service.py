import asyncio
import logging
from datetime import datetime, timezone, timedelta
from threading import Lock
from uuid import uuid4
from sgp4.api import jday
from predictor import find_conjunctions, DEFAULT_REFINEMENT_STEP_SECONDS, DEFAULT_MAX_RELATIVE_SPEED_KM_S
from services.catalog_service import catalog
from services.screening_catalog import prepare_screening_catalog, POLICY
from services.snapshot_store import ScreeningSnapshot, event_id


class ScreeningService:
    def __init__(self):
        self._lock = Lock()
        self._run_lock = Lock()
        self._current = None
        self._store = None
        self._is_running = False
        self._last_error = None

    def configure_store(self, store):
        # Called once during lifespan, before the background worker starts.
        with self._run_lock:
            store.initialize()
            restored = store.latest()
            with self._lock:
                self._store = store
                self._current = restored

    def current_snapshot(self):
        with self._lock:
            return self._current

    def get_snapshot(self, id=None):
        current = self.current_snapshot()
        if id is None or (current and current.id == id):
            return current
        return self._store.get(id) if self._store else None

    def resolve_event(self, id, snapshot_id=None):
        snapshot = self.get_snapshot(snapshot_id)
        if snapshot:
            event = next((e for e in snapshot.events if event_id(e) == id), None)
            if event:
                return snapshot, event
        if snapshot_id is None and self._store:
            snapshot = self._store.find_event(id)
            if snapshot:
                return snapshot, next(e for e in snapshot.events if event_id(e) == id)
        return None

    def snapshot(self):
        current = self.current_snapshot()
        return (list(current.events), current.computed_at) if current else ([], None)

    def get_events(self):
        return self.snapshot()[0]

    def get_last_updated_at(self):
        return self.snapshot()[1]

    def is_running(self):
        with self._lock:
            return self._is_running

    def status(self):
        with self._lock:
            current = self._current
            state = ("running" if self._is_running else "failed" if self._last_error else
                     "ready" if current else "pending")
            return {"state": state, "is_running": self._is_running,
                    "last_updated_at": current.computed_at if current else None,
                    "last_error": self._last_error,
                    "window_start": current.window_start if current else None,
                    "window_end": current.window_end if current else None,
                    "object_count": current.object_count if current else 0,
                    "event_count": len(current.events) if current else 0,
                    "parameters": dict(current.parameters) if current else None,
                    "snapshot_id": current.id if current else None,
                    "is_stale": current.window_end < datetime.now(timezone.utc) if current else None}

    def run_screening(self, threshold_km=50.0, hours=24, timestep_minutes=1,
                      refinement_step_seconds=DEFAULT_REFINEMENT_STEP_SECONDS,
                      max_relative_velocity_km_s=DEFAULT_MAX_RELATIVE_SPEED_KM_S):
        if not self._run_lock.acquire(blocking=False):
            return
        with self._lock:
            self._is_running = True
        try:
            satellites = catalog.get_all()
            if not satellites:
                raise ValueError("No catalog available for screening")
            screening_satellites, aliases = prepare_screening_catalog(satellites)
            now = datetime.now(timezone.utc)
            jd, fr = jday(now.year, now.month, now.day, now.hour, now.minute,
                          now.second + now.microsecond / 1_000_000)
            events = find_conjunctions(satellites=screening_satellites, jd=jd, fr=fr, start_time=now,
                                      threshold_km=threshold_km, minutes=hours * 60,
                                      timestep_minutes=timestep_minutes, refinement_step_seconds=refinement_step_seconds,
                                      max_relative_velocity_km_s=max_relative_velocity_km_s)
            snapshot = ScreeningSnapshot(id=str(uuid4()), computed_at=datetime.now(timezone.utc),
                window_start=now, window_end=now + timedelta(hours=hours), object_count=len(satellites),
                parameters={"algorithm": "sampled-local-minima-v2", "threshold_km": threshold_km,
                    "catalog_filter": POLICY, "screened_object_count": len(screening_satellites),
                    "station_aliases": aliases,
                    "coarse_step_seconds": timestep_minutes * 60,
                    "refinement_step_seconds": refinement_step_seconds,
                    "max_relative_velocity_km_s": max_relative_velocity_km_s},
                events=tuple(sorted(events, key=lambda e: (e.tca, e.sat1.norad_id, e.sat2.norad_id))))
            # Commit to disk first. Failed writes must not publish an undurable result.
            if self._store:
                self._store.save(snapshot)
            with self._lock:
                self._current = snapshot
                self._last_error = None
        except Exception as error:
            with self._lock:
                self._last_error = type(error).__name__
            raise
        finally:
            with self._lock:
                self._is_running = False
            self._run_lock.release()

    async def run_periodically(self, interval_seconds=1800):
        while True:
            await asyncio.sleep(interval_seconds)
            try:
                await asyncio.to_thread(self.run_screening)
            except Exception:
                logging.getLogger(__name__).exception("Screening failed")


screening_service = ScreeningService()
