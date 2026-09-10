from datetime import datetime, timedelta, timezone
from schemas.scene import OrbitalSceneResponse, SceneObject, SceneSample
from services.ephemeris_service import build_ephemeris


def build_orbital_scene(satellites, minutes=100, step_seconds=60, now=None):
    """A coherent, bounded TEME snapshot for client-side orbital visualization."""
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    start = now - timedelta(minutes=minutes / 2)
    end = now + timedelta(minutes=minutes / 2)
    objects = []
    for satellite in sorted(satellites, key=lambda item: item.norad_id):
        ephemeris = build_ephemeris(satellite, start, end, step_seconds, required_times=(now,))
        objects.append(SceneObject(name=satellite.name, norad_id=satellite.norad_id,
            samples=[SceneSample(time=sample.time, position_km=sample.position_km)
                     for sample in ephemeris.samples]))
    return OrbitalSceneResponse(computed_at=now, window_start=start, window_end=end, objects=objects)
