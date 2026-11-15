import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from brand_threat_monitor.storage.database import connect, initialize
from brand_threat_monitor.review.service import open_case, decide
from brand_threat_monitor.lists.service import load_lists, merge_database_lists, evaluate


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        self.ctx=connect(self.root/'db.sqlite3'); self.db=self.ctx.__enter__(); initialize(self.db)
        with self.db:
            self.db.execute("INSERT INTO advertisers VALUES ('fixture','publisher')")
            for ad_id in ['ad1','ad2']:
                self.db.execute("INSERT INTO ads VALUES ('fixture',?,'publisher','2026-11-15','2026-11-15','2026-11-15','{}')",(ad_id,))
        self.case=open_case(self.db,'fixture','ad1',actor='tester')['case_id']
        self.evidence=self.root/'evidence.txt'; self.evidence.write_text('Synthetic evidence')

    def tearDown(self):
        self.ctx.__exit__(None,None,None); self.tmp.cleanup()

    def test_spam_only_affects_one_ad_and_cannot_repeat(self):
        decide(self.db,self.case,'spam',actor='tester',reason='irrelevant',confirm_id='ad1')
        snap=merge_database_lists(self.db,load_lists('lists'))
        self.assertEqual(evaluate({'source':'fixture','ad_id':'ad1','advertiser_id':'publisher'},None,snap)['state'],'discarded_brown')
        self.assertEqual(evaluate({'source':'fixture','ad_id':'ad2','advertiser_id':'publisher'},None,snap)['state'],'pending_review')
        with self.assertRaises(ValueError):
            decide(self.db,self.case,'pending',actor='tester',reason='change')

    def test_attack_records_evidence_and_prioritizes_other_ad(self):
        with self.assertRaises(ValueError):
            decide(self.db,self.case,'attack',actor='tester',reason='attack',confirm_id='publisher')
        decide(self.db,self.case,'attack',actor='tester',reason='documented',confirm_id='publisher',evidence_file=self.evidence)
        snap=merge_database_lists(self.db,load_lists('lists'))
        self.assertEqual(evaluate({'source':'fixture','ad_id':'ad2','advertiser_id':'publisher'},None,snap)['state'],'known_black')
        self.assertEqual(self.db.execute('SELECT count(*) FROM evidence').fetchone()[0],1)

    def test_pending_has_no_list_effect_and_can_later_classify(self):
        decide(self.db,self.case,'pending',actor='tester',reason='need more evidence')
        self.assertEqual(self.db.execute('SELECT count(*) FROM brownlist').fetchone()[0],0)
        decide(self.db,self.case,'spam',actor='tester',reason='irrelevant',confirm_id='ad1')

    def test_audit_failure_rolls_back_decision_and_list(self):
        with patch('brand_threat_monitor.review.service.audit',side_effect=RuntimeError('audit failed')):
            with self.assertRaises(RuntimeError):
                decide(self.db,self.case,'spam',actor='tester',reason='spam',confirm_id='ad1')
        self.assertEqual(self.db.execute('SELECT count(*) FROM brownlist').fetchone()[0],0)
        self.assertIsNone(self.db.execute('SELECT decision FROM review_cases').fetchone()[0])

    def test_wrong_confirmation_and_white_conflict_do_not_modify(self):
        with self.assertRaises(ValueError):
            decide(self.db,self.case,'spam',actor='tester',reason='spam',confirm_id='wrong')
        with self.db:
            self.db.execute("INSERT INTO advertiser_lists VALUES ('white1','fixture','publisher','white','global','trusted','tester','2026-11-15T12:00:00+00:00',1,NULL)")
        with self.assertRaises(ValueError):
            decide(self.db,self.case,'attack',actor='tester',reason='attack',confirm_id='publisher',evidence_file=self.evidence)
        self.assertEqual(self.db.execute('SELECT count(*) FROM evidence').fetchone()[0],0)


if __name__=='__main__': unittest.main()
