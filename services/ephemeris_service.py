from datetime import timedelta, timezone, datetime
import math
from sgp4.api import jday
from schemas.ephemeris import EphemerisResponse, StateSample

MAX_SAMPLES = 721
MAX_DURATION_SECONDS = 6 * 60 * 60


def build_ephemeris(satellite, start, end, step_seconds=60, required_times=()):
    if start.tzinfo is None or end.tzinfo is None:
        raise ValueError("start and end must include a UTC offset")
    start, end = start.astimezone(timezone.utc), end.astimezone(timezone.utc)
    duration = (end - start).total_seconds()
    if duration <= 0 or duration > MAX_DURATION_SECONDS:
        raise ValueError("Window must be greater than zero and at most 6 hours")
    if not 1 <= step_seconds <= 600:
        raise ValueError("step_seconds must be between 1 and 600")
    count = math.ceil(duration / step_seconds) + 1
    if count > MAX_SAMPLES:
        raise ValueError("At most 721 samples; increase step_seconds or shorten the window")
    times = {start + timedelta(seconds=min(index * step_seconds, duration)) for index in range(count)}
    for time in required_times:
        if time.tzinfo is None or not start <= time <= end:
            raise ValueError("Required sample time must be aware and within the window")
        times.add(time.astimezone(timezone.utc))
    if len(times) > MAX_SAMPLES:
        raise ValueError("At most 721 samples including required instants")
    samples = []
    for time in sorted(times):
        jd, fr = jday(time.year, time.month, time.day, time.hour, time.minute,
                      time.second + time.microsecond / 1_000_000)
        position, velocity = satellite.state_at(jd, fr)
        if not all(math.isfinite(value) for value in (*position, *velocity)):
            raise RuntimeError("Propagation returned non-finite values")
        samples.append(StateSample(time=time, position_km=position, velocity_km_s=velocity))
    return EphemerisResponse(norad_id=satellite.norad_id, element_epoch=satellite.epoch,
                             computed_at=datetime.now(timezone.utc), samples=samples)
