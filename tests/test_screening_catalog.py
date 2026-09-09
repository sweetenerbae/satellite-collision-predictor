import json
import unittest
from pathlib import Path
from unittest.mock import patch

from satellite import Satellite
from services.screening_catalog import prepare_screening_catalog, DYNAMIC_FIELDS, POLICY
from services.screening_service import ScreeningService


class ScreeningCatalogTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads((Path(__file__).parent / 'fixtures/station.json').read_text())
        self.station = self.make(25544)

    def make(self, id, **changes):
        return Satellite(dict(self.data, NORAD_CAT_ID=id, **changes))

    def test_aliases_collapse_to_station_and_catalog_is_unchanged(self):
        alias = self.make(36086, OBJECT_NAME='POISK', REV_AT_EPOCH=123)
        objects = [alias, self.station]
        result, aliases = prepare_screening_catalog(objects)
        self.assertEqual(result, [self.station])
        self.assertEqual(aliases, [{'norad_id': 36086, 'representative_norad_id': 25544, 'reason': 'structural_module'}])
        self.assertEqual(objects, [alias, self.station])

    def test_every_changed_dynamic_field_restores_independent_object(self):
        for field in DYNAMIC_FIELDS:
            with self.subTest(field=field):
                other = self.make(67796, **{field: float(self.data[field]) + 1e-10})
                self.assertEqual(prepare_screening_catalog([self.station, other])[0], [self.station, other])

    def test_different_epoch_is_not_an_alias(self):
        other = self.make(67796, EPOCH='2026-01-01T00:00:00.000000')
        self.assertEqual(len(prepare_screening_catalog([self.station, other])[0]), 2)

    def test_names_and_matching_nonstation_orbits_do_not_trigger_filter(self):
        objects = [self.make(60000, OBJECT_NAME='ISS MODULE'), self.make(60001)]
        self.assertEqual(prepare_screening_catalog(objects), (objects, []))

    def test_css_anchor_supported(self):
        station, alias = self.make(48274), self.make(53239)
        self.assertEqual(prepare_screening_catalog([alias, station])[0], [station])

    def test_duplicate_ids_still_rejected(self):
        with self.assertRaises(ValueError):
            prepare_screening_catalog([self.station, self.station])

    def test_service_screens_representatives_and_records_policy(self):
        alias = self.make(36086)
        outsider = self.make(60000, MEAN_ANOMALY=self.data['MEAN_ANOMALY'] + .001)
        service = ScreeningService()
        with patch('services.screening_service.catalog.get_all', return_value=[alias, self.station, outsider]), \
                patch('services.screening_service.find_conjunctions', return_value=[]) as find:
            service.run_screening()
        self.assertEqual(find.call_args.kwargs['satellites'], [self.station, outsider])
        snapshot = service.current_snapshot()
        self.assertEqual(snapshot.object_count, 3)
        self.assertEqual(snapshot.parameters['screened_object_count'], 2)
        self.assertEqual(snapshot.parameters['catalog_filter'], POLICY)
        self.assertEqual(len(snapshot.parameters['station_aliases']), 1)

    def test_modules_with_independent_elements_and_their_aliases_share_parent(self):
        station = self.make(48274)
        module = self.make(53239, MEAN_ANOMALY=self.data['MEAN_ANOMALY'] + .001)
        visitor = self.make(69049, MEAN_ANOMALY=self.data['MEAN_ANOMALY'] + .001)
        reps, aliases = prepare_screening_catalog([station, module, visitor])
        self.assertEqual(reps, [station])
        self.assertEqual({a['representative_norad_id'] for a in aliases}, {48274})

    def test_missing_parent_preserves_module(self):
        module = self.make(53239)
        self.assertEqual(prepare_screening_catalog([module]), ([module], []))
