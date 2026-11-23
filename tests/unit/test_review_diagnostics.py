"""Regression coverage for non-destructive review diagnostics."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from test_database import sample
from brand_threat_monitor.storage.database import connect,initialize
from brand_threat_monitor.storage.repositories import import_result
from brand_threat_monitor.review.diagnostics import diagnose_review
from brand_threat_monitor.review.queue import database_queue,clear_unreviewed
from brand_threat_monitor.review.service import open_case,decide
from brand_threat_monitor.lists.service import load_lists
from brand_threat_monitor.history.filters import Filters


class ReviewDiagnosticTests(unittest.TestCase):
    def setUp(self):
        """Create isolated storage and use the versioned empty list configuration."""
        self.temp=tempfile.TemporaryDirectory();self.database=Path(self.temp.name)/'db.sqlite3'
        self.lists=Path(__file__).resolve().parents[2]/'lists'
        with connect(self.database) as db:initialize(db)

    def tearDown(self):
        """Remove only the temporary diagnostic fixtures."""
        self.temp.cleanup()

    def test_missing_database_does_not_create_storage(self):
        """Read-only diagnostics must not accidentally initialize a different workspace."""
        path=Path(self.temp.name)/'missing'/'db.sqlite3'
        report=diagnose_review(path,self.lists)
        self.assertFalse(report['database_exists']);self.assertFalse(path.parent.exists())

    def test_multiple_searches_are_visible_and_filters_are_explained(self):
        """Both independent query results reach the queue, while country filters are explicit."""
        one=sample();two=copy.deepcopy(one)
        two['run_id']='run2';two['country']='BR';two['ads'][0]['ad_id']='ad2'
        two['observations'][0].update(run_id='run2',ad_id='ad2')
        with connect(self.database) as db:
            import_result(db,one,actor='tester');import_result(db,two,actor='tester')
        report=diagnose_review(self.database,self.lists,filters=Filters(country='CO'))
        self.assertEqual(report['counts']['queue_without_filters'],2)
        self.assertEqual(report['counts']['queue_with_filters'],1)
        self.assertEqual(report['errors'],[])
        self.assertTrue(any('Active UI filters' in f for f in report['findings']))

    def test_classified_and_cleared_ads_explain_empty_queue_without_mutation(self):
        """Diagnostics distinguish review decisions from queue clears and do not write audit rows."""
        one=sample();two=copy.deepcopy(one)
        two['run_id']='run2';two['ads'][0]['ad_id']='ad2';two['observations'][0].update(run_id='run2',ad_id='ad2')
        with connect(self.database) as db:
            import_result(db,one,actor='tester');import_result(db,two,actor='tester')
            case=open_case(db,'fixture','ad1',actor='tester')
            decide(db,case['case_id'],'spam',actor='tester',reason='Fixture',confirm_id='ad1')
            rows=database_queue(db,load_lists(self.lists))['queue']
            clear_unreviewed(db,rows,actor='tester')
            before=[tuple(r) for r in db.execute('SELECT * FROM audit_log')]
        report=diagnose_review(self.database,self.lists)
        self.assertEqual(report['exclusions']['already_classified'],1)
        self.assertEqual(report['exclusions']['cleared_unreviewed'],1)
        self.assertEqual(report['counts']['queue_without_filters'],0)
        with connect(self.database) as db:
            self.assertEqual(before,[tuple(r) for r in db.execute('SELECT * FROM audit_log')])

    def test_history_only_and_missing_query_context_are_detected(self):
        """Historical runs and standalone ads are not misreported as a populated review queue."""
        data=sample();data['ads']=[];data['observations']=[]
        with connect(self.database) as db:import_result(db,data,actor='tester')
        report=diagnose_review(self.database,self.lists)
        self.assertEqual(report['counts']['runs'],1);self.assertEqual(report['counts']['ads'],0)
        self.assertTrue(any('no persisted accepted ads' in f for f in report['findings']))
        with connect(self.database) as db:
            with db:db.execute("INSERT INTO ads VALUES ('fixture','orphan',NULL,'2026-11-23','2026-11-23','2026-11-23','{}')")
        report=diagnose_review(self.database,self.lists)
        self.assertEqual(report['counts']['ads_without_query_context'],1)

    def test_missing_schema_and_invalid_database_are_reported(self):
        """Uninitialized or corrupt storage produces findings without applying migrations."""
        import sqlite3
        blank=Path(self.temp.name)/'blank.sqlite3';sqlite3.connect(blank).close()
        report=diagnose_review(blank,self.lists)
        self.assertIn('queue_clears',report['missing_tables'])
        from contextlib import closing
        with closing(sqlite3.connect(blank)) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM sqlite_master").fetchone()[0],0)
        bad=Path(self.temp.name)/'invalid.sqlite3';bad.write_text('not sqlite',encoding='utf-8')
        report=diagnose_review(bad,self.lists)
        self.assertTrue(report['errors'])
