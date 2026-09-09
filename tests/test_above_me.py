import unittest
from datetime import datetime, timezone
from math import cos, sin

from services.above_me_service import WGS84_A_KM, _gmst_radians, _topocentric


class AboveMeMathTests(unittest.TestCase):
    def test_overhead_position_has_ninety_degree_elevation(self):
        time = datetime(2026, 9, 10, tzinfo=timezone.utc)
        theta = _gmst_radians(time)
        # Make an Earth-fixed position directly above (0°, 0°), then express it as TEME.
        earth_fixed_x = WGS84_A_KM + 500
        teme = (cos(theta) * earth_fixed_x, sin(theta) * earth_fixed_x, 0)
        _, elevation, distance = _topocentric(teme, 0, 0, time)
        self.assertAlmostEqual(elevation, 90, places=6)
        self.assertAlmostEqual(distance, 500, places=6)

    def test_azimuth_is_normalized(self):
        time = datetime(2026, 9, 10, tzinfo=timezone.utc)
        theta = _gmst_radians(time)
        # Earth-fixed point to the east of the observer.
        x, y = WGS84_A_KM, 1000
        teme = (cos(theta) * x - sin(theta) * y, sin(theta) * x + cos(theta) * y, 0)
        azimuth, _, _ = _topocentric(teme, 0, 0, time)
        self.assertAlmostEqual(azimuth, 90, places=6)


if __name__ == '__main__':
    unittest.main()
