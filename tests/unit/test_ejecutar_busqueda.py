"""Pruebas del ejecutor sin consultas de red."""

import unittest
from datetime import datetime, timezone
from types import SimpleNamespace

from ejecutar_busqueda import collect, prepare


class SearchTests(unittest.TestCase):
    def profile(self):
        return {'country': 'co', 'criteria': [{'query': 'pichincha & credito'}],
                'search': {'template_url': 'https://www.facebook.com/ads/library/?start_date[min]=2026-11-13&start_date[max]'}}

    def test_today_replaces_stale_and_empty_dates(self):
        from urllib.parse import parse_qs, urlsplit
        prepared = prepare(self.profile(), now=datetime(2026, 11, 15, 12, tzinfo=timezone.utc))
        query = parse_qs(urlsplit(prepared[1]).query)
        self.assertEqual(query['start_date[min]'], ['2026-11-15'])
        self.assertEqual(query['start_date[max]'], ['2026-11-15'])
        self.assertEqual(query['q'], ['pichincha & credito'])

    def test_local_day_and_inclusive_window(self):
        profile = self.profile()
        profile['days_to_review'] = 7
        prepared = prepare(profile, now=datetime(2026, 11, 15, 2, tzinfo=timezone.utc))
        self.assertEqual(prepared[4].isoformat(), '2026-11-08')
        self.assertEqual(prepared[5].isoformat(), '2026-11-14')

    def test_rejects_ambiguous_or_foreign_url(self):
        for url in ['https://example.com/ads/library/',
                    'https://www.facebook.com/ads/library/?q=a&q=b']:
            with self.assertRaises(ValueError):
                prepare(self.profile(), url)

    def test_failure_keeps_received_ad(self):
        stamp = datetime.now(timezone.utc)
        ad = SimpleNamespace(id='123', delivery_start_time=stamp,
                             page=SimpleNamespace(id='456'), to_dict=lambda: {})

        class FakeCollector:
            stats = {}
            def __init__(self, **kwargs): pass
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def search(self, **kwargs):
                yield ad
                raise RuntimeError('Fallo de paginacion simulado')

        result = collect(self.profile(), collector_factory=FakeCollector)
        self.assertEqual(result['status'], 'partial')
        self.assertEqual(result['ads'][0]['ad_id'], '123')
        self.assertEqual(result['ads'][0]['advertiser_id'], '456')
        self.assertEqual(len(result['errors']), 1)


if __name__ == '__main__':
    unittest.main()
