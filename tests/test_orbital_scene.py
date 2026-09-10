import json
import unittest
from datetime import datetime, timezone
from pathlib import Path
from satellite import Satellite
from services.orbital_scene_service import build_orbital_scene


class OrbitalSceneTests(unittest.TestCase):
    def test_scene_contains_the_requested_current_instant_once(self):
        data = json.loads((Path(__file__).parent / "fixtures/station.json").read_text())
        now = datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc)
        scene = build_orbital_scene([Satellite(data)], minutes=20, step_seconds=90, now=now)
        samples = scene.objects[0].samples
        self.assertEqual(scene.computed_at, now)
        self.assertEqual(sum(sample.time == now for sample in samples), 1)
        self.assertEqual(samples[0].time, scene.window_start)
        self.assertEqual(samples[-1].time, scene.window_end)
