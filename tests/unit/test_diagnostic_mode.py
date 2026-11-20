import unittest
from datetime import datetime,timezone
from brand_threat_monitor.collectors.base import Advertiser,CollectedAd,CollectorCapabilities
from brand_threat_monitor.ingestion.collector import collect


class UnfilteredSource:
    capabilities=CollectorCapabilities(server_date_filter=True)
    stats={}
    def __init__(self,**kwargs): pass
    def __enter__(self): return self
    def __exit__(self,*args): pass
    def search(self,**kwargs):
        for ad_id,stamp in [('old1','2026-05-09T12:00:00+00:00'),('matching','2026-11-17T12:00:00+00:00'),('old2','2026-01-01T12:00:00+00:00')]:
            yield CollectedAd(ad_id,datetime.fromisoformat(stamp),Advertiser('publisher'),
                              {'body':'Full original text '+ad_id,'api_fields':{'source_marker':ad_id}})


class DiagnosticModeTests(unittest.TestCase):
    def profile(self):
        return {'country':'sv','criteria':[{'query':'chivo'}],
                'search':{'template_url':'https://www.facebook.com/ads/library/',
                          'date_range':{'mode':'fixed','min':'2026-11-16','max':'2026-11-17'}}}

    def test_diagnostic_mode_keeps_all_content_and_continues(self):
        result=collect(self.profile(),collector_factory=UnfilteredSource,diagnostic_mode=True)
        self.assertEqual(result['scanned_ads'],3)
        self.assertEqual(result['excluded_by_date'],2)
        self.assertEqual(result['errors'],[])
        self.assertEqual([ad['ad_id'] for ad in result['ads']],['matching'])
        self.assertEqual(len(result['received_ads']),3)
        self.assertEqual(result['received_ads'][0]['content']['body'],'Full original text old1')
        self.assertEqual(result['received_ads'][0]['content']['api_fields']['source_marker'],'old1')
        self.assertEqual(result['received_ads'][0]['date_evaluation']['decision'],'excluded_by_local_date')
        self.assertEqual(result['temporal_filter_status'],'post_filtered_locally')

    def test_normal_mode_also_postfilters_without_emergency_date_stop(self):
        result=collect(self.profile(),collector_factory=UnfilteredSource)
        self.assertEqual(result['scanned_ads'],3)
        self.assertEqual(result['errors'],[])
        self.assertEqual(len(result['received_ads']),3)
        self.assertIsNone(result['server_filters']['start_date'])
        self.assertEqual(result['returned_ads'],1)


if __name__=='__main__': unittest.main()
