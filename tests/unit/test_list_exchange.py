import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from brand_threat_monitor.storage.database import connect,initialize
from brand_threat_monitor.lists.service import ListSnapshot,merge_database_lists
from brand_threat_monitor.lists.exchange import empty_documents,read_lists_file,plan_import,import_lists,export_lists


def white():
    """Build the controlled white fixture used by this test scenario."""
    return {'source':'fixture','advertiser_id':'000123','scope':{'type':'global'},'reason':'=SUM(A1)',
            'reviewer':'tester','created_at':'2026-11-17T12:00:00+00:00','active':True}


class ListExchangeTests(unittest.TestCase):
    def setUp(self):
        """Create isolated test fixtures and resources before each scenario."""
        self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name)
        self.ctx=connect(self.root/'db.sqlite3'); self.db=self.ctx.__enter__(); initialize(self.db)
        self.snapshot=ListSnapshot(empty_documents(),'empty')
        self.docs=empty_documents(); self.docs['whitelist']['entries']=[white()]
        self.source=self.root/'source.json'
        self.source.write_text(json.dumps({'schema_version':'1.0','type':'list_bundle','lists':self.docs}))

    def tearDown(self):
        """Close test resources and remove temporary files after each scenario."""
        self.ctx.__exit__(None,None,None); self.tmp.cleanup()

    def apply(self):
        """Build the controlled apply fixture used by this test scenario."""
        return import_lists(self.db,self.snapshot,self.docs,self.source,self.root/'backups',actor='tester',reason='Reviewed batch')

    def test_preview_has_no_list_or_backup_side_effects(self):
        """Verify that preview has no list or backup side effects."""
        plan=plan_import(self.db,self.snapshot,read_lists_file(self.source))
        self.assertEqual(plan['add_count'],1)
        self.assertEqual(self.db.execute('SELECT count(*) FROM advertiser_lists').fetchone()[0],0)
        self.assertFalse((self.root/'backups').exists())

    def test_import_backs_up_before_change_and_is_idempotent(self):
        """Verify that import backs up before change and is idempotent."""
        result=self.apply()
        self.assertEqual(result['added'],1)
        self.assertTrue((Path(result['backup_path'])/'database.sqlite3').exists())
        again=self.apply(); self.assertTrue(again['already_imported'])
        self.assertEqual(self.db.execute('SELECT count(*) FROM advertiser_lists').fetchone()[0],1)
        self.assertEqual(self.db.execute('SELECT count(*) FROM list_imports').fetchone()[0],1)

    def test_csv_and_json_roundtrip_preserve_ids_and_protected_text(self):
        """Verify that csv and json roundtrip preserve ids and protected text."""
        self.apply()
        for format in ['json','csv']:
            path=export_lists(self.db,self.snapshot,self.root/('lists.'+format))
            restored=read_lists_file(path)
            row=restored['whitelist']['entries'][0]
            self.assertEqual(row['advertiser_id'],'000123')
            self.assertEqual(row['reason'],'=SUM(A1)')
        self.assertIn("'=SUM",(self.root/'lists.csv').read_text(encoding='utf-8-sig'))

    def test_conflict_rejects_entire_batch(self):
        """Verify that conflict rejects entire batch."""
        black=white(); black.update(case_id='unverified',evidence_refs=['unverified'])
        self.docs['blacklist']['entries']=[black]
        with self.assertRaises(ValueError): self.apply()
        self.assertEqual(self.db.execute('SELECT count(*) FROM advertiser_lists').fetchone()[0],0)
        self.assertFalse((self.root/'backups').exists())

    def test_blacklist_requires_verified_existing_case(self):
        """Verify that blacklist requires verified existing case."""
        black=white(); black.update(case_id='unverified',evidence_refs=['unverified'])
        self.docs['whitelist']['entries']=[]; self.docs['blacklist']['entries']=[black]
        with self.assertRaises(ValueError): self.apply()

    def test_backup_failure_prevents_changes(self):
        """Verify that backup failure prevents changes."""
        with patch('brand_threat_monitor.lists.exchange.create_backup',side_effect=OSError('disk full')):
            with self.assertRaises(OSError): self.apply()
        self.assertEqual(self.db.execute('SELECT count(*) FROM advertiser_lists').fetchone()[0],0)

    def test_audit_failure_rolls_back_batch_and_provenance(self):
        """Verify that audit failure rolls back batch and provenance."""
        with patch('brand_threat_monitor.lists.exchange.audit',side_effect=RuntimeError('audit failed')):
            with self.assertRaises(RuntimeError): self.apply()
        self.assertEqual(self.db.execute('SELECT count(*) FROM advertiser_lists').fetchone()[0],0)
        self.assertEqual(self.db.execute('SELECT count(*) FROM list_imports').fetchone()[0],0)

    def test_inactive_entries_require_explicit_deactivation(self):
        """Verify that inactive entries require explicit deactivation."""
        self.docs['whitelist']['entries'][0]['active']=False
        with self.assertRaises(ValueError): plan_import(self.db,self.snapshot,self.docs)


if __name__=='__main__': unittest.main()
