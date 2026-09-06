import math
from datetime import timedelta
from conjunction import ConjunctionEvent

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
