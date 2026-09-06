from data.data_provider import fetch_satellites
from satellite import Satellite
from predictor import find_closest_pair

satellites_data = fetch_satellites()

satellites = []

for data in satellites_data:
    satellite = Satellite(data)
    satellites.append(satellite)

print("Создано спутников:", len(satellites))

for satellite in satellites:
    print(satellite.name, satellite.norad_id)

reference = satellites[0].satrec


jd = reference.jdsatepoch
fr = reference.jdsatepochF

pair, distance = find_closest_pair(satellites, jd, fr)

sat1, sat2 = pair

print()
print("Closest pair:")
print(sat1.name, "<->", sat2.name)
print("Distance:", distance, "km")