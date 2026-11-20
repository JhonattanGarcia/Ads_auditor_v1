import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from test_database import sample
from brand_threat_monitor.storage.database import connect, initialize
from brand_threat_monitor.storage.repositories import import_result
from brand_threat_monitor.review.queue import database_queue, clear_unreviewed
from brand_threat_monitor.review.service import open_case, decide
from brand_threat_monitor.lists.service import load_lists
from brand_threat_monitor.ui.app import ad_start


class QueueClearTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.context=connect(Path(self.temp.name)/'test.sqlite3')
        self.db=self.context.__enter__()
        initialize(self.db)
        import_result(self.db,sample(),actor='tester')
        self.snapshot=load_lists(Path(__file__).resolve().parents[2]/'lists')

    def tearDown(self):
        self.context.__exit__(None,None,None)
        self.temp.cleanup()

    def queue(self):
        return database_queue(self.db,self.snapshot)['queue']

    def test_clear_preserves_data_and_new_observation_returns(self):
        rows=self.queue()
        self.assertEqual(clear_unreviewed(self.db,rows,actor='tester'),1)
        self.assertEqual(self.queue(),[])
        self.assertEqual(clear_unreviewed(self.db,rows,actor='tester'),0)
        for table in ('review_cases','brownlist','advertiser_lists'):
            self.assertEqual(self.db.execute('SELECT count(*) FROM '+table).fetchone()[0],0)
        self.assertEqual(self.db.execute('SELECT count(*) FROM ads').fetchone()[0],1)
        second=copy.deepcopy(sample())
        second['run_id']='run2'
        second['observations'][0].update(run_id='run2',observed_at='2026-11-15T12:00:00+00:00')
        import_result(self.db,second,actor='tester')
        self.assertEqual(len(self.queue()),1)

    def test_explicit_pending_decision_is_preserved_even_with_stale_rows(self):
        rows=self.queue()
        case=open_case(self.db,'fixture','ad1',actor='tester')
        decide(self.db,case['case_id'],'pending',actor='tester',reason='Needs investigation')
        self.assertEqual(clear_unreviewed(self.db,rows,actor='tester'),0)
        self.assertTrue(self.queue()[0]['reviewed'])

    def test_audit_failure_rolls_back(self):
        with patch('brand_threat_monitor.review.service.audit',side_effect=RuntimeError('audit failed')):
            with self.assertRaises(RuntimeError):
                clear_unreviewed(self.db,self.queue(),actor='tester')
        self.assertEqual(len(self.queue()),1)
        self.assertEqual(self.db.execute('SELECT count(*) FROM queue_clears').fetchone()[0],0)

    def test_ad_date_uses_colombia_time_and_handles_missing(self):
        self.assertEqual(ad_start({'delivery_start_time':'2026-11-19T01:00:00+00:00'}).strftime('%Y-%m-%d %H:%M'),'2026-11-18 20:00')
        self.assertIsNone(ad_start({}))
        self.assertIsNone(ad_start({'delivery_start_time':'invalid'}))

    def test_utc_display_preserves_instant(self):
        from brand_threat_monitor.ui.ad_card import card_data
        row={'delivery_start_time':'2026-11-19T01:00:00+00:00'}
        local=ad_start(row)
        utc=ad_start(row,'UTC')
        self.assertEqual(local.timestamp(),utc.timestamp())
        self.assertEqual(utc.strftime('%Y-%m-%d %H:%M'),'2026-11-19 01:00')
        self.assertIn('18 Nov 2026, 20:00',card_data(row)['start'])
        self.assertIn('19 Nov 2026, 01:00',card_data(row,display_timezone='UTC')['start'])
