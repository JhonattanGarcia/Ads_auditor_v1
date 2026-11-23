import copy
import json
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import patch

from brand_threat_monitor.storage.database import connect,initialize
from brand_threat_monitor.lists.service import ListSnapshot,merge_database_lists,evaluate
from brand_threat_monitor.lists.admin import authorize,deactivate,resolve_conflict,list_entries
from brand_threat_monitor.ui.lists import ListsWindow


def entry(identity,value,scope):
    """Build the controlled entry fixture used by this test scenario."""
    return {'source':'fixture',identity:value,'scope':scope,'reason':'Synthetic','reviewer':'tester',
            'created_at':'2026-11-17T12:00:00+00:00','active':True,'case_id':'synthetic','evidence_refs':['synthetic']}


class ListAdminTests(unittest.TestCase):
    def setUp(self):
        """Create isolated test fixtures and resources before each scenario."""
        self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name)
        self.database=self.root/'db.sqlite3'; self.ctx=connect(self.database); self.db=self.ctx.__enter__(); initialize(self.db)
        with self.db: self.db.execute("INSERT INTO clients VALUES ('client1','Client','CO')")
        self.docs={kind:{'schema_version':'1.0','list_type':kind,'identity_fields':['source',key],'entries':[]}
                   for kind,key in [('whitelist','advertiser_id'),('blacklist','advertiser_id'),('brownlist','ad_id')]}
        self.snapshot=ListSnapshot(self.docs,'synthetic')
        self.options={'actor':'tester','reason':'Synthetic administrative review','confirm_id':'publisher'}
        self.ad={'source':'fixture','ad_id':'ad','advertiser_id':'publisher'}

    def tearDown(self):
        """Close test resources and remove temporary files after each scenario."""
        self.ctx.__exit__(None,None,None); self.tmp.cleanup()

    def test_authorize_is_scoped_and_audited(self):
        """Verify that authorize is scoped and audited."""
        authorize(self.db,self.snapshot,'fixture','publisher',{'type':'client','client_id':'client1'},**self.options)
        effective=merge_database_lists(self.db,self.snapshot)
        self.assertEqual(evaluate(self.ad,'client1',effective)['state'],'known_white')
        self.assertEqual(evaluate(self.ad,'another',effective)['state'],'pending_review')
        self.assertEqual(self.db.execute('SELECT operation FROM audit_log').fetchone()[0],'authorize_advertiser')

    def test_json_deactivation_does_not_modify_source_or_reappear(self):
        """Verify that json deactivation does not modify source or reappear."""
        self.docs['whitelist']['entries']=[entry('advertiser_id','publisher',{'type':'global'})]
        original=copy.deepcopy(self.docs)
        deactivate(self.db,self.snapshot,'whitelist','fixture','publisher',{'type':'global'},**self.options)
        self.assertEqual(evaluate(self.ad,'client1',merge_database_lists(self.db,self.snapshot))['state'],'pending_review')
        self.assertEqual(self.docs,original)
        self.assertEqual(self.db.execute('SELECT count(*) FROM list_exclusions').fetchone()[0],1)

    def test_resolution_across_global_and_client_scopes(self):
        """Verify that resolution across global and client scopes."""
        self.docs['whitelist']['entries']=[entry('advertiser_id','publisher',{'type':'client','client_id':'client1'})]
        self.docs['blacklist']['entries']=[entry('advertiser_id','publisher',{'type':'global'})]
        self.assertEqual(evaluate(self.ad,'client1',self.snapshot)['state'],'list_conflict')
        resolve_conflict(self.db,self.snapshot,'fixture','publisher','client1','whitelist',**self.options)
        effective=merge_database_lists(self.db,self.snapshot)
        self.assertEqual(evaluate(self.ad,'client1',effective)['state'],'known_white')
        self.assertEqual(evaluate(self.ad,'another',effective)['state'],'pending_review')

    def test_authorize_requires_explicit_black_conflict_resolution(self):
        """Verify that authorize requires explicit black conflict resolution."""
        self.docs['blacklist']['entries']=[entry('advertiser_id','publisher',{'type':'global'})]
        with self.assertRaises(ValueError): authorize(self.db,self.snapshot,'fixture','publisher',{'type':'global'},**self.options)
        self.assertEqual(self.db.execute('SELECT count(*) FROM advertiser_lists').fetchone()[0],0)

    def test_failed_audit_rolls_back_json_exclusion(self):
        """Verify that failed audit rolls back json exclusion."""
        self.docs['whitelist']['entries']=[entry('advertiser_id','publisher',{'type':'global'})]
        with patch('brand_threat_monitor.lists.admin.audit',side_effect=RuntimeError('failure')):
            with self.assertRaises(RuntimeError): deactivate(self.db,self.snapshot,'whitelist','fixture','publisher',{'type':'global'},**self.options)
        self.assertEqual(self.db.execute('SELECT count(*) FROM list_exclusions').fetchone()[0],0)
        self.assertEqual(evaluate(self.ad,None,merge_database_lists(self.db,self.snapshot))['state'],'known_white')

    def test_ui_loads_entries_without_changes(self):
        """Verify that ui loads entries without changes."""
        folder=self.root/'lists'; folder.mkdir()
        self.docs['whitelist']['entries']=[entry('advertiser_id','publisher',{'type':'global'})]
        for kind,doc in self.docs.items(): (folder/(kind+'.json')).write_text(json.dumps(doc))
        root=tk.Tk(); root.withdraw()
        window=ListsWindow(root,self.database,folder); window.withdraw()
        try:
            self.assertEqual(len(window.table.get_children()),1)
            self.assertEqual(self.db.execute('SELECT count(*) FROM audit_log').fetchone()[0],0)
        finally: window.destroy(); root.destroy()


if __name__=='__main__': unittest.main()
