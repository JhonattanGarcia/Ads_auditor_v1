import copy
import sqlite3
import tempfile
import unittest
from pathlib import Path
from brand_threat_monitor.storage.database import connect, initialize
from brand_threat_monitor.storage.repositories import import_result


def sample():
    return {'schema_version':'1.0','run_id':'run1','source':'fixture',
            'started_at':'2026-11-14T12:00:00+00:00','finished_at':None,
            'status':'partial','coverage':'partial','country':'CO','query':'marca',
            'ads':[{'ad_id':'ad1','source':'fixture','advertiser_id':'publisher1'}],
            'observations':[{'run_id':'run1','source':'fixture','ad_id':'ad1',
                             'observed_at':'2026-11-14T12:00:00+00:00'}]}


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.ctx = connect(Path(self.temp.name)/'monitor.sqlite3')
        self.db = self.ctx.__enter__()
        initialize(self.db)

    def tearDown(self):
        self.ctx.__exit__(None,None,None)
        self.temp.cleanup()

    def count(self, table):
        return self.db.execute('SELECT count(*) FROM '+table).fetchone()[0]

    def test_migration_repeatable_and_foreign_keys_enabled(self):
        initialize(self.db)
        self.assertEqual(self.count('schema_migrations'),2)
        self.assertEqual(self.db.execute('PRAGMA foreign_keys').fetchone()[0],1)
        self.assertEqual(self.db.execute('PRAGMA journal_mode').fetchone()[0],'wal')

    def test_reimport_is_idempotent(self):
        data=sample()
        self.assertTrue(import_result(self.db,data,actor='tester')['imported'])
        self.assertFalse(import_result(self.db,data,actor='tester')['imported'])
        self.assertEqual(self.count('ads'),1)
        self.assertEqual(self.count('ad_observations'),1)
        self.assertEqual(self.count('audit_log'),1)

    def test_two_runs_share_ad_and_keep_observations(self):
        data=sample()
        import_result(self.db,data,actor='tester')
        second=copy.deepcopy(data)
        second['run_id']='run2'
        second['observations'][0].update(run_id='run2', observed_at='2026-11-15T12:00:00+00:00')
        import_result(self.db,second,actor='tester')
        self.assertEqual(self.count('ads'),1)
        self.assertEqual(self.count('ad_observations'),2)
        row=self.db.execute('SELECT * FROM ads').fetchone()
        self.assertTrue(row['first_observed_at'].startswith('2026-11-14'))
        self.assertTrue(row['last_observed_at'].startswith('2026-11-15'))

    def test_invalid_record_rolls_back_entire_run(self):
        data=sample()
        data['ads'].append({'ad_id':42})
        with self.assertRaises(ValueError):
            import_result(self.db,data,actor='tester')
        for table in ('runs','ads','advertisers','audit_log'):
            self.assertEqual(self.count(table),0)

    def test_modified_run_rejected_and_audit_is_immutable(self):
        data=sample()
        import_result(self.db,data,actor='tester')
        data['query']='changed'
        with self.assertRaises(ValueError):
            import_result(self.db,data,actor='tester')
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute('DELETE FROM audit_log')
        self.db.rollback()
        self.assertEqual(self.count('audit_log'),1)


if __name__=='__main__':
    unittest.main()
