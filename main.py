from data.data_provider import fetch_satellites
from satellite import Satellite
from predictor import find_closest_approach, refine_closest_approach
from datetime import datetime, timezone
from datetime import timedelta
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

#conjunction candidate
pair, distance, minute = find_closest_approach(satellites, jd,fr)

sat1, sat2 = pair

precise_distance, second = refine_closest_approach(sat1, sat2, jd, fr, minute)

tca = now + timedelta(seconds=second)

print("Closest approach:")
print(sat1.name, "<->", sat2.name)
print("coarse distance:", distance, "km")
print("precise distance:", precise_distance, "km")
print("TCA UTC:", tca.strftime("%Y-%m-%d %H:%M:%S UTC"))