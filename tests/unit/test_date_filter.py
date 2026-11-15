import json
import unittest
from unittest.mock import Mock
from brand_threat_monitor.collectors.date_filter import install_date_filter


class DateFilterTests(unittest.TestCase):
    def test_every_page_keeps_range_without_changing_cursor(self):
        client=Mock()
        client._build_graphql_payload.side_effect=lambda **kw:kw
        events=[]
        original=install_date_filter(client,'2026-11-14','2026-11-15',events.append)
        for cursor in [None,'page2','page3']:
            variables={'startDate':None,'cursor':cursor,'countries':['SV'],'queryString':'chivo'}
            payload=client._build_graphql_payload('doc',variables,'AdLibrarySearchPaginationQuery')
            self.assertEqual(payload['variables']['startDate'],{'min':'2026-11-14','max':'2026-11-15'})
            self.assertEqual(payload['variables']['cursor'],cursor)
            self.assertIsNone(variables['startDate'])
        self.assertEqual([e['has_cursor'] for e in events],[False,True,True])

    def test_empty_maximum_becomes_null(self):
        client=Mock(); client._build_graphql_payload.side_effect=lambda **kw:kw
        install_date_filter(client,'2026-11-14',None)
        payload=client._build_graphql_payload('doc',{},'AdLibrarySearchPaginationQuery')
        self.assertIsNone(payload['variables']['startDate']['max'])

    def test_other_queries_are_not_modified(self):
        client=Mock(); client._build_graphql_payload.side_effect=lambda **kw:kw
        install_date_filter(client,'2026-11-14','2026-11-15')
        payload=client._build_graphql_payload('doc',{'adArchiveID':'test'},'AdLibraryV3AdDetailsQuery')
        self.assertNotIn('startDate',payload['variables'])

    def test_ignored_server_filter_stops_before_next_record(self):
        from datetime import datetime,timezone
        from brand_threat_monitor.collectors.base import CollectedAd,CollectorCapabilities
        from brand_threat_monitor.ingestion.collector import collect
        class IgnoredFilter:
            capabilities=CollectorCapabilities(server_date_filter=True)
            stats={}
            def __init__(self,**kwargs): pass
            def __enter__(self): return self
            def __exit__(self,*args): pass
            def search(self,**kwargs):
                assert kwargs['start_date']=='2026-11-14'
                assert kwargs['end_date']=='2026-11-14'
                yield CollectedAd('old',datetime(2025,1,1,tzinfo=timezone.utc),None,{})
                raise AssertionError('Pagination must stop before requesting more records')
        profile={'country':'sv','criteria':[{'query':'chivo'}],
                 'search':{'template_url':'https://www.facebook.com/ads/library/',
                           'date_range':{'mode':'fixed','min':'2026-11-14','max':'2026-11-14'}}}
        result=collect(profile,collector_factory=IgnoredFilter)
        self.assertEqual(result['scanned_ads'],1)
        self.assertEqual(result['temporal_filter_status'],'server_filter_not_respected')
        self.assertEqual(result['errors'][0]['type'],'ServerDateFilterMismatch')

    def test_invalid_range_rejected(self):
        with self.assertRaises(ValueError): install_date_filter(Mock(),'2026-11-15','2026-11-14')


if __name__=='__main__': unittest.main()
