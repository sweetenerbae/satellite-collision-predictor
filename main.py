from data.data_provider import fetch_satellites
from satellite import Satellite
from predictor import find_conjunctions, build_spatial_grid, screening_radius_km, neighbor_radius_for_screening, find_candidate_pairs
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

candidates = find_candidate_pairs(
    satellites,
    jd,
    fr
)

print("Candidate pairs:", len(candidates))

for pair in candidates:
    print(pair)

cell_size_km = 100.0
timestep_seconds = 60

radius_km = screening_radius_km(
    threshold_km=50.0,
    timestep_seconds=timestep_seconds
)

neighbor_radius = neighbor_radius_for_screening(
    screening_radius=radius_km,
    cell_size_km=cell_size_km
)

print("Screening radius:", radius_km)
print("Neighbor radius:", neighbor_radius)

print("Conjunction candidates:", len(conjunctions))

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
        event.tca.strftime("%Y-%m-%d %H:%M:%S UTC")
    )

grid = build_spatial_grid(
    satellites,
    jd,
    fr
)

print("Occupied cells:", len(grid))

for cell, objects in grid.items():
    if len(objects) > 1:
        print(cell, [sat.name for sat in objects])