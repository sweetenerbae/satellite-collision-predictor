import math
from datetime import timedelta
from conjunction import ConjunctionEvent
from scipy.spatial import cKDTree

# расстояние
def distance_between(pos1, pos2):
    dx = pos2[0] - pos1[0]
    dy = pos2[1] - pos1[1]
    dz = pos2[2] - pos1[2]

    return math.sqrt(dx**2 + dy**2 + dz**2)

# относительная скорость
def relative_velocity(vel1, vel2):
    dvx = vel2[0] - vel1[0]
    dvy = vel2[1] - vel1[1]
    dvz = vel2[2] - vel1[2]

    return math.sqrt(dvx ** 2 + dvy ** 2 + dvz ** 2)

def refine_closest_approach(sat1, sat2, jd, fr, coarse_minute):
    min_distance = float("inf")
    best_second = None

    start_second = coarse_minute * 60 - 60
    end_second = coarse_minute * 60 + 60

    for second in range(start_second, end_second + 1):
        current_fr = fr + second / 86400.0

        pos1 = sat1.position_at(jd, current_fr)
        pos2 = sat2.position_at(jd, current_fr)

        distance = distance_between(pos1, pos2)

        if distance < min_distance:
            min_distance = distance
            best_second = second

    return min_distance, best_second

#narrow phase
def find_conjunctions(satellites, jd, fr, start_time, threshold_km=50, minutes=1440):
    events = []
    checked_pairs = 0

    for i in range(len(satellites)):
        for j in range(i + 1, len(satellites)):
            sat1 = satellites[i]
            sat2 = satellites[j]
            altitude1 = sat1.approximate_altitude_km()
            altitude2 = sat2.approximate_altitude_km()

            if abs(altitude1 - altitude2) > 100:
                continue

            checked_pairs += 1

            min_distance = float("inf")
            closest_minute = None

            for minute in range(minutes):
                current_fr = fr + minute / 1440.0

                pos1 = sat1.position_at(jd, current_fr)
                pos2 = sat2.position_at(jd, current_fr)

                distance = distance_between(pos1, pos2)

                if distance < 1.0:
                    continue

                if distance < min_distance:
                    min_distance = distance
                    closest_minute = minute

            if closest_minute is None:
                continue

            if min_distance >= threshold_km:
                continue

            precise_distance, precise_second = refine_closest_approach(
                sat1,
                sat2,
                jd,
                fr,
                closest_minute
            )

            tca_fr = fr + precise_second / 86400.0

            _, velocity1 = sat1.state_at(jd, tca_fr)
            _, velocity2 = sat2.state_at(jd, tca_fr)

            rel_velocity = relative_velocity(
                velocity1,
                velocity2
            )

            tca = start_time + timedelta(seconds=precise_second)

            event = ConjunctionEvent(
                sat1=sat1,
                sat2=sat2,
                distance_km=precise_distance,
                relative_velocity_km_s=rel_velocity,
                tca=tca
            )

            events.append(event)

    events.sort(key=lambda event: event.distance_km)
    print("Pairs after altitude filter:", checked_pairs)
    return events

def spatial_cell(position, cell_size_km=100.0):
    x, y, z = position

    return (
        int(x // cell_size_km),
        int(y // cell_size_km),
        int(z // cell_size_km)
    )

def build_spatial_grid(satellites, jd, fr, cell_size_km=100.0):
    grid = {}

    for satellite in satellites:
        position = satellite.position_at(jd, fr)

        cell = spatial_cell(position, cell_size_km)

        if cell not in grid:
            grid[cell] = []

        grid[cell].append(satellite)

    return grid

def neighbouring_cells(cell, radius=1):
    x, y, z = cell
    neighbours = []

    for dx in range(-radius, radius + 1):
      for dy in range(-radius, radius + 1):
         for dz in range(-radius, radius + 1):
             neighbours.append((x+dx, y+dy,z+dz))
    return neighbours

def candidate_pairs_from_grid(grid, neighbor_radius=1):
    pairs = set()

    for cell, satellites in grid.items():
        nearby_cells = neighbouring_cells(
            cell,
            radius=neighbor_radius
        )

        for nearby_cell in nearby_cells:
            nearby_satellites = grid.get(nearby_cell, [])

            for sat1 in satellites:
                for sat2 in nearby_satellites:
                    if sat1 is sat2:
                        continue

                    pair = tuple(
                        sorted(
                            (sat1.norad_id, sat2.norad_id)
                        )
                    )

                    pairs.add(pair)

    return pairs

#broad phase
def find_candidate_pairs(
    satellites,
    jd,
    fr,
    threshold_km=50.0,
    minutes=1440,
    timestep_minutes=1,
    max_relative_velocity_km_s=15.0
):
    candidate_pairs = {}

    timestep_seconds = timestep_minutes * 60

    screening_radius = screening_radius_km(
        threshold_km,
        timestep_seconds,
        max_relative_velocity_km_s
    )

    for minute in range(
        0,
        minutes,
        timestep_minutes
    ):
        current_fr = fr + minute / 1440.0

        pairs_now = candidate_pairs_at_time(
            satellites,
            jd,
            current_fr,
            screening_radius
        )

        for pair in pairs_now:
            if pair not in candidate_pairs:
                candidate_pairs[pair] = []

            candidate_pairs[pair].append(minute)
    return candidate_pairs

def screening_radius_km(
    threshold_km,
    timestep_seconds,
    max_relative_velocity_km_s=15.0
):
    return threshold_km + max_relative_velocity_km_s * timestep_seconds


def neighbor_radius_for_screening(
    screening_radius,
    cell_size_km
):
    return math.ceil(screening_radius / cell_size_km)

def screening_radius_km(
    threshold_km,
    timestep_seconds,
    max_relative_velocity_km_s=15.0
):
    return (
        threshold_km
        + max_relative_velocity_km_s * timestep_seconds
    )

def neighbor_radius_for_screening(
    screening_radius,
    cell_size_km
):
    return math.ceil(
        screening_radius / cell_size_km
    )


def candidate_pairs_at_time(
    satellites,
    jd,
    fr,
    screening_radius_km
):
    positions = []

    for satellite in satellites:
        position = satellite.position_at(jd, fr)
        positions.append(position)

    tree = cKDTree(positions)

    index_pairs = tree.query_pairs(
        r=screening_radius_km
    )

    candidate_pairs = set()

    for i, j in index_pairs:
        sat1 = satellites[i]
        sat2 = satellites[j]

        pair = (
            min(sat1.norad_id, sat2.norad_id),
            max(sat1.norad_id, sat2.norad_id)
        )

        candidate_pairs.add(pair)

    return candidate_pairs