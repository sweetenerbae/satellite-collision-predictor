import asyncio
from datetime import datetime, timezone
from threading import Lock
from data.data_provider import fetch_satellites
from satellite import Satellite


class SatelliteCatalog:
    def __init__(self):
        self._lock = Lock()
        self._satellites = []
        self._satellites_by_id = {}
        self._loaded_at = None
        self._last_error = None

    def load(self):
        try:
            satellites = [Satellite(data) for data in fetch_satellites()]
            by_id = {item.norad_id: item for item in satellites}
            if not satellites or len(by_id) != len(satellites):
                raise ValueError("Catalog is empty or contains duplicate NORAD IDs")
        except Exception as error:
            with self._lock:
                self._last_error = type(error).__name__
            raise
        with self._lock:
            self._satellites = satellites
            self._satellites_by_id = by_id
            self._loaded_at = datetime.now(timezone.utc)
            self._last_error = None

    async def refresh_periodically(self, interval_seconds=7200):
        while True:
            await asyncio.sleep(interval_seconds)
            try:
                await asyncio.to_thread(self.load)
            except Exception:
                import logging
                logging.getLogger(__name__).exception("Catalog refresh failed; keeping previous snapshot")

    def get_all(self):
        with self._lock:
            return list(self._satellites)

    def get_by_id(self, norad_id):
        with self._lock:
            return self._satellites_by_id.get(norad_id)

    def status(self):
        with self._lock:
            return {"ready": bool(self._satellites), "object_count": len(self._satellites),
                    "loaded_at": self._loaded_at, "last_error": self._last_error,
                    "source": "CelesTrak", "group": "STATIONS"}


catalog = SatelliteCatalog()
