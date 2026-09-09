"""Immutable calculation snapshots. SQLite transactions publish a whole run at once."""
import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from uuid import uuid5, NAMESPACE_URL

from conjunction import ConjunctionEvent
from satellite import Satellite


def event_id(event):
    pair = sorted([event.sat1.norad_id, event.sat2.norad_id])
    return str(uuid5(NAMESPACE_URL, f"satellite:{pair[0]}:{pair[1]}:{event.tca.isoformat()}"))


@dataclass(frozen=True)
class ScreeningSnapshot:
    id: str
    computed_at: datetime
    window_start: datetime
    window_end: datetime
    object_count: int
    parameters: dict
    events: tuple


def encode_snapshot(snapshot):
    objects = {}
    events = []
    for event in snapshot.events:
        for obj in (event.sat1, event.sat2):
            key = str(obj.norad_id)
            elements = obj.omm_data
            if key in objects and objects[key] != elements:
                raise ValueError("Conflicting elements for the same NORAD ID in one snapshot")
            objects[key] = elements
        events.append({
            "satellite_1": str(event.sat1.norad_id), "satellite_2": str(event.sat2.norad_id),
            "distance_km": event.distance_km, "relative_velocity_km_s": event.relative_velocity_km_s,
            "tca": event.tca.isoformat(), "tca_location": event.tca_location,
        })
    return json.dumps({
        "format_version": 1, "id": snapshot.id, "computed_at": snapshot.computed_at.isoformat(),
        "window_start": snapshot.window_start.isoformat(), "window_end": snapshot.window_end.isoformat(),
        "object_count": snapshot.object_count, "parameters": snapshot.parameters,
        "objects": objects, "events": events,
    }, allow_nan=False, separators=(",", ":"))


def decode_snapshot(payload):
    data = json.loads(payload)
    if data["format_version"] != 1:
        raise ValueError("Unsupported snapshot format")
    objects = {key: Satellite(elements) for key, elements in data["objects"].items()}
    events = tuple(ConjunctionEvent(
        sat1=objects[event["satellite_1"]], sat2=objects[event["satellite_2"]],
        distance_km=event["distance_km"], relative_velocity_km_s=event["relative_velocity_km_s"],
        tca=datetime.fromisoformat(event["tca"]), tca_location=event["tca_location"],
    ) for event in data["events"])
    return ScreeningSnapshot(id=data["id"], computed_at=datetime.fromisoformat(data["computed_at"]),
        window_start=datetime.fromisoformat(data["window_start"]),
        window_end=datetime.fromisoformat(data["window_end"]), object_count=data["object_count"],
        parameters=data["parameters"], events=events)


class SnapshotStore:
    def __init__(self, path):
        self.path = Path(path)

    @contextmanager
    def connection(self):
        conn = sqlite3.connect(str(self.path), timeout=10)
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def initialize(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as conn:
            version = conn.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, 1):
                raise ValueError("Unsupported snapshot database version")
            conn.execute("""CREATE TABLE IF NOT EXISTS snapshots (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                id TEXT UNIQUE NOT NULL, payload TEXT NOT NULL)""")
            conn.execute("""CREATE TABLE IF NOT EXISTS snapshot_events (
                snapshot_id TEXT NOT NULL REFERENCES snapshots(id),
                event_id TEXT NOT NULL,
                PRIMARY KEY (snapshot_id, event_id))""")
            conn.execute("CREATE INDEX IF NOT EXISTS event_lookup ON snapshot_events(event_id)")
            conn.execute("PRAGMA user_version = 1")

    def save(self, snapshot):
        payload = encode_snapshot(snapshot)
        with self.connection() as conn:
            conn.execute("INSERT INTO snapshots(id,payload) VALUES (?,?)", (snapshot.id, payload))
            conn.executemany("INSERT INTO snapshot_events(snapshot_id,event_id) VALUES (?,?)",
                             [(snapshot.id, event_id(event)) for event in snapshot.events])

    def latest(self):
        with self.connection() as conn:
            row = conn.execute("SELECT payload FROM snapshots ORDER BY sequence DESC LIMIT 1").fetchone()
        return decode_snapshot(row[0]) if row else None

    def get(self, snapshot_id):
        with self.connection() as conn:
            row = conn.execute("SELECT payload FROM snapshots WHERE id=?", (snapshot_id,)).fetchone()
        return decode_snapshot(row[0]) if row else None

    def find_event(self, id):
        # Resolve the latest retained snapshot containing the event, not the current catalog.
        with self.connection() as conn:
            row = conn.execute("""SELECT s.payload FROM snapshots s
                JOIN snapshot_events e ON e.snapshot_id=s.id WHERE e.event_id=?
                ORDER BY s.sequence DESC LIMIT 1""", (id,)).fetchone()
        return decode_snapshot(row[0]) if row else None
