import math
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from predictor import find_conjunctions

START = datetime(2026, 9, 8, tzinfo=timezone.utc)


class AnalyticSatellite:
    """Synthetic trajectories with independently known extrema, not orbital fixtures."""
    def __init__(self, norad_id, position, velocity=lambda t: (0., 0., 0.)):
        self.norad_id = norad_id
        self.name = str(norad_id)
        self.position = position
        self.velocity = velocity
        self.sampled = []

    def state_at(self, jd, fr):
        t = (jd - 2451545.0 + fr) * 86400
        self.sampled.append(t)
        return self.position(t), self.velocity(t)

    def position_at(self, jd, fr):
        return self.state_at(jd, fr)[0]


def stationary():
    return AnalyticSatellite(1, lambda t: (0., 0., 0.))


def linear(tca, miss=2., speed=1.):
    return AnalyticSatellite(2, lambda t: (speed*(t-tca), miss, 0.),
                             lambda t: (speed, 0., 0.))


class PredictorTests(unittest.TestCase):
    def search(self, other, **kwargs):
        return find_conjunctions([stationary(), other], 2451545., 0., START, **kwargs)

    def test_repeated_minima_in_one_continuous_candidate_window(self):
        other = AnalyticSatellite(2, lambda t: (10*math.cos(math.pi*t/120), 2., 0.),
                                  lambda t: (-math.pi/12*math.sin(math.pi*t/120), 0., 0.))
        events = self.search(other, minutes=6, threshold_km=5)
        self.assertEqual(len(events), 3)
        for event, seconds in zip(events, [60, 180, 300]):
            self.assertAlmostEqual((event.tca-START).total_seconds(), seconds, delta=0.01)
            self.assertAlmostEqual(event.distance_km, 2., places=5)

    def test_tca_and_velocity_between_coarse_samples(self):
        events = self.search(linear(37.125, speed=4), minutes=2, threshold_km=3)
        self.assertEqual(len(events), 1)
        self.assertAlmostEqual((events[0].tca-START).total_seconds(), 37.125, delta=0.01)
        self.assertAlmostEqual(events[0].relative_velocity_km_s, 4.)

    def test_closed_window_end_and_no_propagation_outside(self):
        other = linear(130)
        events = self.search(other, minutes=2, threshold_km=20)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].tca, START+timedelta(seconds=120))
        self.assertEqual(events[0].tca_location, "window_end")
        self.assertTrue(all(0 <= t <= 120.000001 for t in other.sampled))

    def test_window_start(self):
        events = self.search(linear(-10), minutes=2, threshold_km=20)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].tca, START)
        self.assertEqual(events[0].tca_location, "window_start")

    def test_minimum_near_boundary(self):
        for tca in [0.125, 119.875]:
            with self.subTest(tca=tca):
                events = self.search(linear(tca), minutes=2, threshold_km=3)
                self.assertEqual(len(events), 1)
                self.assertAlmostEqual((events[0].tca-START).total_seconds(), tca, delta=0.01)

    def test_co_moving_pair_is_not_silently_discarded(self):
        other = AnalyticSatellite(2, lambda t: (.5, 0., 0.))
        events = self.search(other, minutes=2, threshold_km=1)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].distance_km, .5)
        self.assertEqual(events[0].tca, START)

    def test_threshold_is_inclusive(self):
        events = self.search(linear(30, miss=5), minutes=1, threshold_km=5)
        self.assertEqual(len(events), 1)

    def test_fractional_duration_and_nondefault_step(self):
        events = self.search(linear(76), minutes=1.25, timestep_minutes=.4, threshold_km=3)
        self.assertEqual(events[0].tca, START+timedelta(seconds=75))

    def test_reject_invalid_configuration_and_duplicates(self):
        for kwargs in [dict(minutes=0), dict(minutes=float('nan')), dict(threshold_km=-1),
                       dict(timestep_minutes=0), dict(refinement_step_seconds=0)]:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self.search(linear(30), **kwargs)
        with self.assertRaises(ValueError):
            find_conjunctions([stationary(), stationary()], 2451545., 0., START)
        with self.assertRaises(ValueError):
            find_conjunctions([], 2451545., 0., START.replace(tzinfo=None))

    def test_nonfinite_propagation_fails_calculation(self):
        for position in [(float('nan'),0,0), (float('inf'),0,0)]:
            with self.subTest(position=position), self.assertRaises(RuntimeError):
                self.search(AnalyticSatellite(2, lambda t: position), minutes=1)

    def test_early_co_motion_does_not_hide_a_later_minimum(self):
        def position(t):
            return (.5 - .3*math.exp(-((t-900)/30)**2), 0., 0.)
        def velocity(t):
            return (.6*(t-900)/900*math.exp(-((t-900)/30)**2), 0., 0.)
        events = self.search(AnalyticSatellite(2, position, velocity), minutes=20, threshold_km=1)
        later = [event for event in events if event.tca_location == "interior"]
        self.assertEqual(len(later), 1)
        self.assertAlmostEqual((later[0].tca-START).total_seconds(), 900, delta=.01)
        self.assertAlmostEqual(later[0].distance_km, .2)

    def test_speed_bound_and_optimizer_failure_are_explicit(self):
        with self.assertRaises(RuntimeError):
            self.search(linear(30, speed=4), minutes=1, max_relative_velocity_km_s=3)
        failure = type('Failure', (), {'success': False})()
        with patch('predictor.minimize_scalar', return_value=failure):
            with self.assertRaises(RuntimeError):
                self.search(linear(30), minutes=1)

    def test_overlapping_candidate_padding_does_not_duplicate_event(self):
        with patch('predictor.find_candidate_pairs', return_value={(1,2): [(0,0), (2,2)]}):
            events = self.search(linear(60), minutes=3, threshold_km=3)
        self.assertEqual(len(events), 1)
        self.assertAlmostEqual((events[0].tca-START).total_seconds(), 60, delta=.01)

    def test_sgp4_against_independent_one_second_distance_scan(self):
        import json
        from pathlib import Path
        from satellite import Satellite
        from sgp4.api import jday
        fixture = json.loads((Path(__file__).parent / 'fixtures/station.json').read_text())
        other = dict(fixture, OBJECT_NAME='Synthetic nearby orbit', NORAD_CAT_ID=50000)
        other['MEAN_ANOMALY'] += .02
        other['RA_OF_ASC_NODE'] += .03
        pair = [Satellite(fixture), Satellite(other)]
        start = datetime.fromisoformat(fixture['EPOCH']).replace(tzinfo=timezone.utc)
        jd, fr = jday(start.year,start.month,start.day,start.hour,start.minute,
                      start.second+start.microsecond/1e6)
        events = find_conjunctions(pair,jd,fr,start,minutes=180,threshold_km=50)
        values = [math.dist(pair[0].position_at(jd,fr+t/86400),
                            pair[1].position_at(jd,fr+t/86400)) for t in range(10801)]
        minima = [i for i in range(1,len(values)-1) if values[i]<values[i-1] and values[i]<values[i+1]]
        interior = [e for e in events if e.tca_location == 'interior']
        self.assertGreater(len(minima), 1)
        self.assertEqual(len(interior),len(minima))
        for event, second in zip(interior,minima):
            self.assertAlmostEqual((event.tca-start).total_seconds(),second,delta=1)
            self.assertLessEqual(event.distance_km,values[second]+1e-6)
