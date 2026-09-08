import asyncio
import logging
from datetime import datetime, timezone, timedelta
from threading import Lock
from sgp4.api import jday
from predictor import find_conjunctions
from services.catalog_service import catalog


class ScreeningService:
    def __init__(self):
        self._lock = Lock()
        self._run_lock = Lock()
        self._events = []
        self._last_updated_at = None
        self._is_running = False
        self._last_error = None
        self._window_start = None
        self._window_end = None
        self._object_count = 0

    def snapshot(self):
        with self._lock:
            return list(self._events), self._last_updated_at

    def get_events(self):
        return self.snapshot()[0]

    def get_last_updated_at(self):
        return self.snapshot()[1]

    def is_running(self):
        with self._lock:
            return self._is_running

    def status(self):
        with self._lock:
            state = ("running" if self._is_running else "failed" if self._last_error else
                     "ready" if self._last_updated_at else "pending")
            return {"state": state, "is_running": self._is_running,
                    "last_updated_at": self._last_updated_at, "last_error": self._last_error,
                    "window_start": self._window_start, "window_end": self._window_end,
                    "object_count": self._object_count, "event_count": len(self._events)}

    def run_screening(self, threshold_km=50.0, hours=24):
        if not self._run_lock.acquire(blocking=False):
            return
        with self._lock:
            self._is_running = True
        try:
            satellites = catalog.get_all()
            if not satellites:
                raise ValueError("No catalog available for screening")
            now = datetime.now(timezone.utc)
            jd, fr = jday(now.year, now.month, now.day, now.hour, now.minute,
                          now.second + now.microsecond / 1_000_000)
            events = find_conjunctions(satellites=satellites, jd=jd, fr=fr, start_time=now,
                                      threshold_km=threshold_km, minutes=hours * 60)
            with self._lock:
                self._events = sorted(events, key=lambda event: event.tca)
                self._last_updated_at = datetime.now(timezone.utc)
                self._window_start = now
                self._window_end = now + timedelta(hours=hours)
                self._object_count = len(satellites)
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
