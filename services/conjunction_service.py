from datetime import datetime, timezone

from sgp4.api import jday

from data.data_provider import fetch_satellites
from satellite import Satellite
from predictor import find_conjunctions
from services.satellite_service import get_satellites

def get_conjunctions(
    threshold_km: float,
    hours: int
):
    satellites = get_satellites()

    now = datetime.now(timezone.utc)

    jd, fr = jday(
        now.year,
        now.month,
        now.day,
        now.hour,
        now.minute,
        now.second + now.microsecond / 1_000_000
    )

    return find_conjunctions(
        satellites=satellites,
        jd=jd,
        fr=fr,
        start_time=now,
        threshold_km=threshold_km,
        minutes=hours * 60
    )