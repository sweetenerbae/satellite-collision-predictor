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