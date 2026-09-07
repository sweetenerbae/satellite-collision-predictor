import math
from datetime import timedelta
from conjunction import ConjunctionEvent
from scipy.spatial import cKDTree
from scipy.optimize import minimize_scalar
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

    screening_windows = {}

    for pair, minutes_found in candidate_pairs.items():
        screening_windows[pair] = compress_minutes_to_windows(
            minutes_found,
            timestep_minutes
        )

    return screening_windows

def screening_radius_km(
    threshold_km,
    timestep_seconds,
    max_relative_velocity_km_s=15.0
):
    return threshold_km + max_relative_velocity_km_s * timestep_seconds

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

def compress_minutes_to_windows(minutes, timestep_minutes=1):
    if not minutes:
        return []

    minutes = sorted(minutes)

    windows = []

    start = minutes[0]
    end = minutes[0]

    for minute in minutes[1:]:
        if minute - end <= timestep_minutes:
            end = minute
        else:
            windows.append((start, end))
            start = minute
            end = minute

    windows.append((start, end))

    return windows

def analyze_screening_window(
    sat1,
    sat2,
    jd,
    fr,
    window_start_minute,
    window_end_minute
):
    start_second = max(
        0,
        window_start_minute * 60 - 60
    )

    end_second = (
        window_end_minute * 60 + 60
    )

    def distance_at_second(second):
        current_fr = fr + second / 86400.0

        pos1 = sat1.position_at(jd, current_fr)
        pos2 = sat2.position_at(jd, current_fr)

        return distance_between(pos1, pos2)

    result = minimize_scalar(
        distance_at_second,
        bounds=(start_second, end_second),
        method="bounded"
    )

    precise_second = result.x
    precise_distance = result.fun

    return precise_distance, precise_second
def is_persistent_co_moving_pair(
    sat1,
    sat2,
    jd,
    fr,
    check_minutes=10,
    max_distance_km=1.0,
    max_relative_velocity_km_s=0.01
):
    sample_minutes = [0, check_minutes // 2, check_minutes]

    for minute in sample_minutes:
        current_fr = fr + minute / 1440.0

        pos1, vel1 = sat1.state_at(jd, current_fr)
        pos2, vel2 = sat2.state_at(jd, current_fr)

        distance = distance_between(pos1, pos2)
        rel_velocity = relative_velocity(vel1, vel2)

        if distance > max_distance_km:
            return False

        if rel_velocity > max_relative_velocity_km_s:
            return False

    return True

def find_conjunctions(
    satellites,
    jd,
    fr,
    start_time,
    threshold_km=50.0,
    minutes=1440,
    timestep_minutes=1
):
    events = []

    satellites_by_id = {
        satellite.norad_id: satellite
        for satellite in satellites
    }

    screening_windows = find_candidate_pairs(
        satellites=satellites,
        jd=jd,
        fr=fr,
        threshold_km=threshold_km,
        minutes=minutes,
        timestep_minutes=timestep_minutes
    )

    for pair, windows in screening_windows.items():
        norad_id_1, norad_id_2 = pair

        sat1 = satellites_by_id[norad_id_1]
        sat2 = satellites_by_id[norad_id_2]

        if is_persistent_co_moving_pair(
                sat1,
                sat2,
                jd,
                fr
        ):
            continue

        for window_start, window_end in windows:
            precise_distance, precise_second = analyze_screening_window(
                sat1=sat1,
                sat2=sat2,
                jd=jd,
                fr=fr,
                window_start_minute=window_start,
                window_end_minute=window_end
            )

            if precise_distance >= threshold_km:
                continue

            tca_fr = fr + precise_second / 86400.0

            _, velocity1 = sat1.state_at(jd, tca_fr)
            _, velocity2 = sat2.state_at(jd, tca_fr)

            rel_velocity = relative_velocity(
                velocity1,
                velocity2
            )

            tca = start_time + timedelta(
                seconds=precise_second
            )

            event = ConjunctionEvent(
                sat1=sat1,
                sat2=sat2,
                distance_km=precise_distance,
                relative_velocity_km_s=rel_velocity,
                tca=tca
            )

            events.append(event)

    events.sort(
        key=lambda event: event.distance_km
    )

    return events