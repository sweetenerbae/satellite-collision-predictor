"""Topocentric directions for the current station catalog.

The SGP4 states are TEME.  This endpoint uses a documented GMST rotation to
produce an observer-relative direction.  It is suitable for an on-device
finder overlay; precision pointing requires a full TEME-to-ITRF transform.
"""
from datetime import datetime, timezone
from math import atan2, cos, degrees, hypot, pi, sin, sqrt
from sgp4.api import jday
from schemas.above_me import AboveMeObject, AboveMeResponse

WGS84_A_KM = 6378.137
WGS84_E2 = 6.69437999014e-3


def _gmst_radians(time):
    jd, fr = jday(time.year, time.month, time.day, time.hour, time.minute,
                  time.second + time.microsecond / 1_000_000)
    centuries = (jd + fr - 2451545.0) / 36525.0
    seconds = (67310.54841 + (876600 * 3600 + 8640184.812866) * centuries
               + 0.093104 * centuries ** 2 - 6.2e-6 * centuries ** 3)
    return (seconds % 86400.0) * pi / 43200.0


def _observer_ecef(latitude, longitude):
    sin_lat = sin(latitude)
    radius = WGS84_A_KM / sqrt(1 - WGS84_E2 * sin_lat * sin_lat)
    return (radius * cos(latitude) * cos(longitude),
            radius * cos(latitude) * sin(longitude),
            radius * (1 - WGS84_E2) * sin_lat)


def _topocentric(position_teme, latitude_deg, longitude_deg, time):
    latitude, longitude = latitude_deg * pi / 180.0, longitude_deg * pi / 180.0
    theta = _gmst_radians(time)
    x, y, z = position_teme
    # TEME -> Earth-fixed via GMST; the response declares this approximation.
    x, y = cos(theta) * x + sin(theta) * y, -sin(theta) * x + cos(theta) * y
    ox, oy, oz = _observer_ecef(latitude, longitude)
    dx, dy, dz = x - ox, y - oy, z - oz
    east = -sin(longitude) * dx + cos(longitude) * dy
    north = -sin(latitude) * cos(longitude) * dx - sin(latitude) * sin(longitude) * dy + cos(latitude) * dz
    up = cos(latitude) * cos(longitude) * dx + cos(latitude) * sin(longitude) * dy + sin(latitude) * dz
    horizontal = hypot(east, north)
    return (degrees(atan2(east, north)) % 360.0,
            degrees(atan2(up, horizontal)), hypot(horizontal, up))


def objects_above_observer(satellites, latitude_deg, longitude_deg, now=None):
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    jd, fr = jday(now.year, now.month, now.day, now.hour, now.minute,
                  now.second + now.microsecond / 1_000_000)
    objects = []
    for satellite in satellites:
        position, _ = satellite.state_at(jd, fr)
        azimuth, elevation, range_km = _topocentric(position, latitude_deg, longitude_deg, now)
        if elevation >= 0:
            objects.append(AboveMeObject(name=satellite.name, norad_id=satellite.norad_id,
                azimuth_deg=azimuth, elevation_deg=elevation, range_km=range_km))
    return AboveMeResponse(computed_at=now, observer_latitude_deg=latitude_deg,
        observer_longitude_deg=longitude_deg,
        objects=sorted(objects, key=lambda item: (-item.elevation_deg, item.range_km, item.norad_id)))
