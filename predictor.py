import math

# расстояние
def distance_between(pos1, pos2):
    dx = pos2[0] - pos1[0]
    dy = pos2[1] - pos1[1]
    dz = pos2[2] - pos1[2]

    return math.sqrt(dx**2 + dy**2 + dz**2)

# ближайшая пара
def find_closest_pair(satellites, jd, fr):
    min_distance = float("inf")
    closest_pair = None

    for i in range(len(satellites)):
        for j in range(i + 1, len(satellites)):
            sat1 = satellites[i]
            sat2 = satellites[j]

            pos1 = sat1.position_at(jd, fr)
            pos2 = sat2.position_at(jd, fr)

            distance = distance_between(pos1, pos2)
            if distance < 1.0:
                continue

            if distance < min_distance:
                min_distance = distance
                closest_pair = (sat1, sat2)

    return closest_pair, min_distance

def find_closest_approach(satellites, jd, fr, minutes=1440):
    min_distance = float("inf")
    closest_pair = None
    closest_minute = None

    for minute in range(minutes):
        current_fr = fr + minute / 1440.0

        for i in range(len(satellites)):
            for j in range(i + 1, len(satellites)):
                sat1 = satellites[i]
                sat2 = satellites[j]

                pos1 = sat1.position_at(jd, current_fr)
                pos2 = sat2.position_at(jd, current_fr)

                distance = distance_between(pos1, pos2)

                if distance < 1.0:
                    continue

                if distance < min_distance:
                    min_distance = distance
                    closest_pair = (sat1, sat2)
                    closest_minute = minute

    return closest_pair, min_distance, closest_minute

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

def find_conjunctions(satellites, jd, fr, threshold_km=50, minutes=1440):
    conjunctions = []

    for i in range(len(satellites)):
        for j in range(i + 1, len(satellites)):
            sat1 = satellites[i]
            sat2 = satellites[j]

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

            if min_distance < threshold_km:
                conjunctions.append({
                    "sat1": sat1,
                    "sat2": sat2,
                    "distance": min_distance,
                    "minute": closest_minute
                })

    return conjunctions