"""Verifica el contrato de fuente sin llamadas de red."""

import unittest
from datetime import datetime, timezone
from pathlib import Path
from threading import Event
from unittest.mock import patch

from brand_threat_monitor.collectors.base import CollectorCancelled, CollectorError
from brand_threat_monitor.collectors.fixture import FixtureCollector
from brand_threat_monitor.collectors.meta import MetaCollector
from ejecutar_busqueda import collect

FIXTURE = Path(__file__).resolve().parents[1] / 'fixtures/collector_ads.json'


class CollectorTests(unittest.TestCase):
    def test_fixture_preserves_ids_and_missing_fields(self):
        with FixtureCollector(FIXTURE) as collector:
            ads = list(collector.search(query='marca ficticia', country='CO', max_results=3))
        self.assertEqual(len(ads), 3)
        self.assertEqual(ads[0].page.id, ads[1].page.id)
        self.assertIsNone(ads[2].delivery_start_time)
        copy = ads[0].to_dict()
        copy['body'] = 'changed'
        self.assertNotEqual(ads[0].to_dict()['body'], 'changed')

    def test_failure_does_not_remove_emitted_results(self):
        collector = FixtureCollector(FIXTURE, fail_after=1)
        stream = collector.search(query='marca ficticia', country='CO', max_results=3)
        self.assertEqual(next(stream).id, 'fixture_ad_001')
        with self.assertRaises(CollectorError):
            next(stream)

    def test_cancellation_before_first_result(self):
        event = Event()
        event.set()
        with self.assertRaises(CollectorCancelled):
            next(FixtureCollector(FIXTURE).search(query='marca', country='CO',
                                                 max_results=3, cancel_event=event))

    def test_fixture_pipeline_records_partial_failure(self):
        profile = {'country': 'co', 'criteria': [{'query': 'marca ficticia'}],
                   'search': {'template_url': 'https://www.facebook.com/ads/library/',
                              'date_range': {'mode': 'fixed', 'min': '2026-11-14', 'max': '2026-11-14'}}}
        result = collect(profile, collector_factory=lambda **kw: FixtureCollector(FIXTURE, fail_after=2))
        self.assertEqual(result['status'], 'partial')
        self.assertEqual(result['ads'][0]['ad_id'], 'fixture_ad_002')
        self.assertEqual(result['excluded_by_date'], 1)
        self.assertEqual(result['errors'][0]['type'], 'CollectorError')

    def test_meta_adapter_normalizes_model_and_error(self):
        from types import SimpleNamespace
        vendor_ad = SimpleNamespace(id='abc', delivery_start_time=datetime.now(timezone.utc),
                                    page=SimpleNamespace(id='publisher'), to_dict=lambda: {'body': 'example'})
        def stream(**kw):
            yield vendor_ad
            raise RuntimeError('network failed')
        with patch('meta_ads_collector.MetaAdsCollector') as backend:
            backend.return_value.search.side_effect = stream
            with MetaCollector() as collector:
                iterator = collector.search(query='example', country='CO', max_results=2)
                self.assertEqual(next(iterator).page.id, 'publisher')
                with self.assertRaises(CollectorError):
                    next(iterator)


if __name__ == '__main__':
    unittest.main()
