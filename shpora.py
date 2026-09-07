# шпаргалка для разработки
from sgp4.api import Satrec
import math

#mks
line1 = "1 25544U 98067A   26249.46623009  .00004151  00000+0  83451-4 0  9998"
line2 = "2 25544  51.6308 257.8166 0005026 113.2307 246.9211 15.49006161584353"
satellite = Satrec.twoline2rv(line1, line2)

inclination_degrees = math.degrees(satellite.inclo)
raan_degrees = math.degrees(satellite.nodeo)
revolutions_per_minute = satellite.no_kozai / (2 * math.pi)
revolutions_per_day = revolutions_per_minute * 1440
period_minutes = 1440 / revolutions_per_day
jd = satellite.jdsatepoch #julian date
fr = satellite.jdsatepochF #fraction дробная часть суток
error_code, position, velocity = satellite.sgp4(jd, fr)

print(inclination_degrees) # наклонение орбиты
print(raan_degrees) # RAAN
print(satellite.ecco) # эксцентриситет
print(satellite.no_kozai) # inclination среднее число оборотов спутника вокруг земли за сутки
print("Оборотов в сутки:", revolutions_per_day)
print("Один оборот, минут:", period_minutes)
print("julian date:", jd)
print('fraction:', fr)
print("\nError:", error_code)
print("position:", position)
print("velocity:", velocity)

# расстояние между спутниками - d = √((x2-x1)² + (y2-y1)² + (z2-z1)²)
# формула расстояния между двумя точками в 3d

#tianhe
line1_t = "1 48274U 21035A   26249.26095405  .00013514  00000+0  16863-3 0  9990"
line2_t = "2 48274  41.4675 189.8186 0002350 260.0025 100.0548 15.59622579305827"
station2 = satellite.twoline2rv(line1_t, line2_t)
_, pos1, _ = satellite.sgp4(jd, fr)
_, pos2, _ = station2.sgp4(jd, fr)

dx = pos2[0] - pos1[0]
dy = pos2[1] - pos1[1]
dz = pos2[2] - pos1[2]

distance = math.sqrt(dx**2 + dy**2 + dz**2)

print("расстояние:", distance, "km")

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
