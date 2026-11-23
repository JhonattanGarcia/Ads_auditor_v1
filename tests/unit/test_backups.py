import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from brand_threat_monitor.backups.service import create_backup, restore_backup
from brand_threat_monitor.config.operator import set_operator, resolve_actor
from brand_threat_monitor.storage.database import connect, initialize


class BackupTests(unittest.TestCase):
    def test_snapshot_includes_committed_wal_and_restores_audit(self):
        """Verify that snapshot includes committed wal and restores audit."""
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            with connect(root/'live.sqlite3') as db:
                initialize(db)
                with db:
                    db.execute("INSERT INTO clients VALUES ('test','Prueba','CO')")
                backup=create_backup(root/'live.sqlite3',root/'backups',actor='tester')
                target=restore_backup(backup,root/'restored.sqlite3',actor='restorer')
                with connect(target) as restored:
                    self.assertEqual(restored.execute('SELECT count(*) FROM clients').fetchone()[0],1)
                    self.assertEqual(restored.execute("SELECT actor FROM audit_log WHERE operation='restore_backup'").fetchone()[0],'restorer')
                with self.assertRaises(ValueError):
                    restore_backup(backup,target,actor='tester')

    def test_tampering_rejected_without_target(self):
        """Verify that tampering rejected without target."""
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            with connect(root/'live.sqlite3') as db:
                initialize(db)
            backup=create_backup(root/'live.sqlite3',root/'backups',actor='tester')
            with (backup/'database.sqlite3').open('ab') as stream:
                stream.write(b'tampered')
            with self.assertRaises(ValueError):
                restore_backup(backup,root/'restored.sqlite3',actor='tester')
            self.assertFalse((root/'restored.sqlite3').exists())

    def test_missing_source_is_not_created(self):
        """Verify that missing source is not created."""
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            with self.assertRaises(ValueError):
                create_backup(root/'missing.sqlite3',root/'backups',actor='tester')
            self.assertFalse((root/'missing.sqlite3').exists())

    def test_operator_persistence_override_and_validation(self):
        """Verify that operator persistence override and validation."""
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'operator.json'
            with self.assertRaises(ValueError): resolve_actor(path=path)
            set_operator(' analyst ',path)
            self.assertEqual(resolve_actor(path=path),'analyst')
            self.assertEqual(resolve_actor('override',path),'override')
            with self.assertRaises(ValueError): set_operator('  ',path)
            self.assertEqual(resolve_actor(path=path),'analyst')


if __name__=='__main__': unittest.main()
