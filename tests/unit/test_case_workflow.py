import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from brand_threat_monitor.storage.database import connect, initialize
from brand_threat_monitor.review.service import open_case, decide, reopen_case, case_detail
from brand_threat_monitor.review.reports import record_report
from brand_threat_monitor.review.queue import database_queue
from brand_threat_monitor.lists.service import load_lists


class CaseWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name)
        self.ctx=connect(self.root/'db'); self.db=self.ctx.__enter__(); initialize(self.db)
        with self.db:
            self.db.execute("INSERT INTO advertisers VALUES ('fixture','publisher')")
            self.db.execute("INSERT INTO runs VALUES ('run','2026-11-15',NULL,'partial','fixture','1','partial','{}')")
            self.db.execute("INSERT INTO run_queries VALUES ('query','run',NULL,'CO','test',NULL,NULL)")
            for ad in ['ad1','ad2']:
                self.db.execute("INSERT INTO ads VALUES ('fixture',?,'publisher','2026-11-15','2026-11-15','2026-11-15','{}')",(ad,))
                self.db.execute("INSERT INTO ad_observations VALUES ('run','fixture',?,'2026-11-15')",(ad,))
                self.db.execute("INSERT INTO observation_queries VALUES ('run','fixture',?,'query')",(ad,))
        self.case=open_case(self.db,'fixture','ad1',actor='tester')['case_id']
        self.evidence=self.root/'proof.txt'; self.evidence.write_text('Synthetic')

    def tearDown(self):
        self.ctx.__exit__(None,None,None); self.tmp.cleanup()

    def test_correct_spam_reopens_queue_preserving_history(self):
        decide(self.db,self.case,'spam',actor='tester',reason='spam',confirm_id='ad1')
        self.assertEqual(len(database_queue(self.db,load_lists('lists'))['queue']),1)
        reopen_case(self.db,self.case,actor='reviewer',reason='Mistaken identity',confirm_case_id=self.case)
        self.assertEqual(len(database_queue(self.db,load_lists('lists'))['queue']),2)
        detail=case_detail(self.db,self.case)
        self.assertEqual(len(detail['events']),3)
        self.assertIsNone(detail['case']['decision'])
        self.assertEqual(self.db.execute('SELECT active FROM brownlist').fetchone()[0],0)

    def test_correct_attack_keeps_other_confirmed_antecedent(self):
        second=open_case(self.db,'fixture','ad2',actor='tester')['case_id']
        for case in [self.case,second]:
            decide(self.db,case,'attack',actor='tester',reason='proof',confirm_id='publisher',evidence_file=self.evidence)
        reopen_case(self.db,self.case,actor='reviewer',reason='correction',confirm_case_id=self.case)
        row=self.db.execute('SELECT * FROM advertiser_lists').fetchone()
        self.assertEqual(row['active'],1)
        self.assertEqual(row['case_id'],second)
        reopen_case(self.db,second,actor='reviewer',reason='second correction',confirm_case_id=second)
        self.assertEqual(self.db.execute('SELECT active FROM advertiser_lists').fetchone()[0],0)
        self.assertEqual(self.db.execute('SELECT count(*) FROM evidence').fetchone()[0],2)

    def test_correction_failure_rolls_back_all_changes(self):
        decide(self.db,self.case,'spam',actor='tester',reason='spam',confirm_id='ad1')
        with patch('brand_threat_monitor.review.service.audit',side_effect=RuntimeError('failure')):
            with self.assertRaises(RuntimeError):
                reopen_case(self.db,self.case,actor='tester',reason='correction',confirm_case_id=self.case)
        self.assertEqual(self.db.execute('SELECT active FROM brownlist').fetchone()[0],1)

    def test_report_does_not_change_classification(self):
        record_report(self.db,self.case,actor='tester',reported_at='2026-11-14T12:00:00-05:00',status='sent',reason='Reported externally')
        detail=case_detail(self.db,self.case)
        self.assertIsNone(detail['case']['decision'])
        self.assertEqual(detail['reports'][0]['status'],'sent')
        with self.assertRaises(ValueError):
            record_report(self.db,self.case,actor='tester',reported_at='2026-11-14T12:00:00-05:00',status='action_confirmed',reason='missing confirmation')

    def test_report_audit_failure_rolls_back(self):
        with patch('brand_threat_monitor.review.reports.audit',side_effect=RuntimeError('failure')):
            with self.assertRaises(RuntimeError):
                record_report(self.db,self.case,actor='tester',reported_at='2026-11-14T12:00:00-05:00',status='sent',reason='report')
        self.assertEqual(self.db.execute('SELECT count(*) FROM report_events').fetchone()[0],0)


if __name__=='__main__': unittest.main()
