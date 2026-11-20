import unittest
from brand_threat_monitor.search.post_filter import post_filter


def record(ad_id,stamp,source='fixture'):
    return {'content':{'source':source,'ad_id':ad_id,'delivery_start_time':stamp,'body':'text'},
            'observed_at':'2026-11-17T12:00:00+00:00'}


class PostFilterTests(unittest.TestCase):
    def filter(self,rows):
        return post_filter(rows,minimum='2026-11-16',maximum='2026-11-17',timezone='America/Bogota',run_id='run')

    def test_inclusive_local_boundaries(self):
        rows=[record('before','2026-11-16T04:59:59+00:00'),record('first','2026-11-16T05:00:00+00:00'),
              record('last','2026-11-18T04:59:59+00:00'),record('after','2026-11-18T05:00:00+00:00')]
        result=self.filter(rows)
        self.assertEqual([a['ad_id'] for a in result['ads']],['last','first'])
        self.assertEqual(result['excluded_by_date'],2)

    def test_newest_first_and_deterministic_ties(self):
        rows=[record('z','2026-11-16T12:00:00+00:00'),record('a','2026-11-17T12:00:00+00:00'),
              record('b','2026-11-17T12:00:00+00:00')]
        result=self.filter(rows)
        self.assertEqual([a['ad_id'] for a in result['ads']],['a','b','z'])
        self.assertEqual([a['ad_id'] for a in result['observations']],['a','b','z'])

    def test_duplicates_use_source_and_ad_identity(self):
        rows=[record('same','2026-11-17T12:00:00+00:00'),record('same','2026-11-17T12:00:00+00:00'),
              record('same','2026-11-17T12:00:00+00:00','other')]
        result=self.filter(rows)
        self.assertEqual(len(result['ads']),2)
        self.assertEqual(result['duplicates_skipped'],1)
        self.assertEqual(len(rows),3)

    def test_invalid_dates_and_identity_are_separate(self):
        rows=[record(None,'2026-11-17T12:00:00+00:00'),record('missing',None),
              record('naive','2026-11-17T12:00:00'),record('broken','invalid')]
        result=self.filter(rows)
        self.assertEqual(len(result['invalid_records']),4)
        self.assertEqual(result['excluded_by_date'],0)
        self.assertEqual(result['ads'],[])

    def test_old_record_does_not_stop_later_matches(self):
        rows=[record('old','2026-01-01T12:00:00+00:00'),record('recent','2026-11-17T12:00:00+00:00')]
        result=self.filter(rows)
        self.assertEqual(result['ads'][0]['ad_id'],'recent')
        self.assertEqual(len(result['scanned_ad_diagnostics']),2)


if __name__=='__main__': unittest.main()
