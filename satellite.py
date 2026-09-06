from sgp4.api import Satrec
from sgp4 import omm

class Satellite:
    def __init__(self, data):
        self.name = data["OBJECT_NAME"]
        self.norad_id = data["NORAD_CAT_ID"]
        self.satrec = Satrec()
        omm.initialize(self.satrec, data)

    def position_at(self, jd, fr):
        error, position, velocity = self.satrec.sgp4(jd, fr)

        if error != 0:
            raise RuntimeError(f"SGP4 error {error} for {self.name}")

        return position

    def state_at(self, jd, fr):
        error, position, velocity = self.satrec.sgp4(jd, fr)

        if error != 0:
            raise RuntimeError(f"SGP4 error {error} for {self.name}")
        # где находится, как жвижется
        return position, velocity

    def approximate_altitude_km(self):
        mu = 398600.4418
        mean_motion_rad_s = self.satrec.no_kozai / 60.0
        semi_major_axis = ( mu / (mean_motion_rad_s ** 2) ) ** (1 / 3)

        earth_radius = 6378.137

        return semi_major_axis - earth_radius