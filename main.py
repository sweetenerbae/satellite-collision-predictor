from data.data_provider import fetch_satellites
from satellite import Satellite
from predictor import refine_closest_approach, find_conjunctions
from datetime import datetime, timezone, timedelta
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
    satellites,
    jd,
    fr,
    threshold_km=50
)

conjunctions.sort(key=lambda event: event["distance"])

print("Conjunction candidates:", len(conjunctions))

for event in conjunctions:
    sat1 = event["sat1"]
    sat2 = event["sat2"]
    coarse_minute = event["minute"]

    precise_distance, precise_second = refine_closest_approach(sat1, sat2, jd, fr, coarse_minute)

    tca = now + timedelta(seconds=precise_second)

    print()
    print(sat1.name, "<->", sat2.name)
    print("coarse distance:", round(event["distance"], 3), "km")
    print("precise distance:", round(precise_distance, 3), "km")
    print("TCA UTC:", tca.strftime("%Y-%m-%d %H:%M:%S UTC"))