import json
import tempfile
import unittest
from pathlib import Path
from brand_threat_monitor.backups.workspace import create_workspace_backup,restore_workspace_backup,verify_workspace_backup
from brand_threat_monitor.backups.service import digest
from brand_threat_monitor.storage.database import connect,initialize


class WorkspaceBackupTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name)
        self.workspace=self.root/'workspace'; self.workspace.mkdir()
        self.database=self.workspace/'data/database/monitor.sqlite3'
        with connect(self.database) as db:
            initialize(db)
            with db:
                db.execute("INSERT INTO ads VALUES ('fixture','ad',NULL,'2026-11-15','2026-11-15','2026-11-15','{}')")
                db.execute("INSERT INTO review_cases(case_id,source,ad_id,reviewer,status) VALUES ('case','fixture','ad','tester','pending_review')")
        for path,data in [('profiles/local/profile.json',{'example':True}),('lists/whitelist.json',{'entries':[]}),
                          ('data/search_list.json',{'type':'editable_search_list','profiles':[],'output_directory':'old'})]:
            p=self.workspace/path; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(data))
        self.external=self.root/'external-proof.txt'; self.external.write_text('Synthetic evidence')
        with connect(self.database) as db:
            with db:
                db.execute("INSERT INTO evidence(evidence_id,case_id,type,hash,local_path) VALUES ('proof','case','local_file',?,?)",(digest(self.external),str(self.external)))
        self.backups=self.root/'backups'

    def tearDown(self): self.tmp.cleanup()

    def backup(self):
        return create_workspace_backup(self.workspace,self.backups,actor='tester')

    def test_roundtrip_includes_profiles_lists_and_external_evidence(self):
        backup=self.backup()
        manifest=verify_workspace_backup(backup)
        target=restore_workspace_backup(backup,self.root/'restored',actor='restorer')
        self.assertEqual(json.loads((target/'profiles/local/profile.json').read_text()),{'example':True})
        self.assertTrue((target/'lists/whitelist.json').exists())
        self.assertEqual(json.loads((target/'data/search_list.json').read_text())['output_directory'],str(target/'data/results'))
        with connect(target/'data/database/monitor.sqlite3') as db:
            path=Path(db.execute("SELECT local_path FROM evidence WHERE evidence_id='proof'").fetchone()[0])
            self.assertTrue(path.is_relative_to(target))
            self.assertEqual(path.read_text(),'Synthetic evidence')
            self.assertEqual(db.execute("SELECT actor FROM audit_log WHERE operation='restore_workspace'").fetchone()[0],'restorer')
        self.assertEqual(self.external.read_text(),'Synthetic evidence')

    def test_changed_file_is_rejected(self):
        backup=self.backup()
        (backup/'profiles/local/profile.json').write_text('altered')
        with self.assertRaises(ValueError): restore_workspace_backup(backup,self.root/'restored',actor='tester')
        self.assertFalse((self.root/'restored').exists())

    def test_missing_referenced_evidence_fails_backup(self):
        self.external.unlink()
        with self.assertRaises(ValueError): self.backup()
        self.assertEqual(list(self.backups.iterdir()),[])

    def test_existing_target_and_unsafe_manifest_are_rejected(self):
        backup=self.backup()
        with self.assertRaises(ValueError): restore_workspace_backup(backup,self.workspace,actor='tester')
        manifest=json.loads((backup/'manifest.json').read_text())
        manifest['members'].append({'path':'../outside','size':0,'sha256':'unused'})
        (backup/'manifest.json').write_text(json.dumps(manifest))
        with self.assertRaises(ValueError): restore_workspace_backup(backup,self.root/'new',actor='tester')
        self.assertFalse((self.root/'new').exists())

    def test_backup_directory_cannot_be_inside_evidence(self):
        with self.assertRaises(ValueError):
            create_workspace_backup(self.workspace,self.workspace/'data/evidence/backups',actor='tester')


if __name__=='__main__': unittest.main()
