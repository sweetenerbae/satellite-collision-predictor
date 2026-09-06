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