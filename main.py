from data.data_provider import fetch_satellites
from satellite import Satellite
from predictor import find_conjunctions
from datetime import datetime, timezone
from sgp4.api import jday

satellites_data = fetch_satellites()

satellites = []

for data in satellites_data:
    satellite = Satellite(data)
    satellites.append(satellite)

print("Создано спутников:", len(satellites))

for satellite in satellites:
    print(satellite.name, satellite.norad_id)

now = datetime.now(timezone.utc)

jd, fr = jday(
    now.year,
    now.month,
    now.day,
    now.hour,
    now.minute,
    now.second + now.microsecond / 1_000_000
)

conjunctions = find_conjunctions(
    satellites=satellites,
    jd=jd,
    fr=fr,
    start_time=now,
    threshold_km=50.0
)

print("\nConjunction candidates:", len(conjunctions))

for event in conjunctions:
    print()
    print(event.sat1.name, "<->", event.sat2.name)
    print("Distance:", round(event.distance_km, 3), "km")
    print(
        "Relative velocity:",
        round(event.relative_velocity_km_s, 3),
        "km/s"
    )
    print(
        "TCA UTC:",
        event.tca.strftime("%Y-%m-%d %H:%M:%S.%f UTC")
    )
