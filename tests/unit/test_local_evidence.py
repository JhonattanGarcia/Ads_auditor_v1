import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image

from brand_threat_monitor.evidence.service import load_preview,attach_image
from brand_threat_monitor.storage.database import connect,initialize
from brand_threat_monitor.ui.evidence import EvidenceWindow


class LocalEvidenceTests(unittest.TestCase):
    def setUp(self):
        """Create isolated test fixtures and resources before each scenario."""
        self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name)
        self.image=self.root/'image.png'; Image.new('RGB',(40,30),'blue').save(self.image)
        self.database=self.root/'data/database/monitor.sqlite3'
        self.ctx=connect(self.database); self.db=self.ctx.__enter__(); initialize(self.db)
        with self.db:
            self.db.execute("INSERT INTO ads VALUES ('fixture','ad',NULL,'2026-11-17','2026-11-17','2026-11-17','{}')")
            self.db.execute("INSERT INTO review_cases(case_id,source,ad_id,reviewer,status) VALUES ('case','fixture','ad','tester','pending_review')")

    def tearDown(self):
        """Close test resources and remove temporary files after each scenario."""
        self.ctx.__exit__(None,None,None); self.tmp.cleanup()

    def test_preview_detects_real_format_and_preserves_original(self):
        """Verify that preview detects real format and preserves original."""
        renamed=self.root/'image.bin'; renamed.write_bytes(self.image.read_bytes())
        before=renamed.read_bytes(); preview=load_preview(renamed)
        self.assertEqual(preview.format,'PNG')
        self.assertEqual((preview.width,preview.height),(40,30))
        self.assertEqual(renamed.read_bytes(),before)

    def test_remote_and_missing_files_rejected(self):
        """Verify that remote and missing files rejected."""
        for value in ['https://example.com/image.png','file:///C:/image.png',r'\\server\share\image.png',str(self.root/'missing.png')]:
            with self.subTest(value=value),self.assertRaises(ValueError): load_preview(value)

    def test_byte_and_pixel_limits(self):
        """Verify that byte and pixel limits."""
        with patch('brand_threat_monitor.evidence.service.MAX_BYTES',8):
            with self.assertRaises(ValueError): load_preview(self.image)
        with patch('brand_threat_monitor.evidence.service.MAX_PIXELS',10):
            with self.assertRaises(ValueError): load_preview(self.image)

    def test_corrupt_or_nonimage_rejected(self):
        """Verify that corrupt or nonimage rejected."""
        invalid=self.root/'fake.png'; invalid.write_text('<html>not an image</html>')
        with self.assertRaises(ValueError): load_preview(invalid)

    def test_attach_copies_audits_and_checks_hash(self):
        """Verify that attach copies audits and checks hash."""
        directory=self.root/'data/evidence'
        evidence_id=attach_image(self.db,'case',self.image,directory,actor='tester',reason='Synthetic screenshot')
        row=self.db.execute('SELECT * FROM evidence WHERE evidence_id=?',(evidence_id,)).fetchone()
        path=Path(row['local_path'])
        self.assertTrue(path.is_relative_to(directory))
        self.assertEqual(path.read_bytes(),self.image.read_bytes())
        load_preview(path,expected_hash=row['hash'])
        self.assertEqual(self.db.execute('SELECT operation FROM audit_log').fetchone()[0],'attach_image')
        path.write_bytes(path.read_bytes()+b'altered')
        with self.assertRaises(ValueError): load_preview(path,expected_hash=row['hash'])

    def test_failed_audit_removes_managed_copy(self):
        """Verify that failed audit removes managed copy."""
        directory=self.root/'data/evidence'
        with patch('brand_threat_monitor.evidence.service.audit',side_effect=RuntimeError('audit failure')):
            with self.assertRaises(RuntimeError):
                attach_image(self.db,'case',self.image,directory,actor='tester',reason='Synthetic')
        self.assertEqual(self.db.execute('SELECT count(*) FROM evidence').fetchone()[0],0)
        self.assertEqual(list(directory.iterdir()),[])

    def test_unknown_case_leaves_no_copy(self):
        """Verify that unknown case leaves no copy."""
        directory=self.root/'data/evidence'
        with self.assertRaises(ValueError): attach_image(self.db,'unknown',self.image,directory,actor='tester',reason='test')
        self.assertFalse(directory.exists())

    def test_ui_requires_explicit_preview(self):
        """Verify that ui requires explicit preview."""
        evidence_id=attach_image(self.db,'case',self.image,self.root/'data/evidence',actor='tester',reason='Synthetic')
        root=tk.Tk(); root.withdraw()
        window=EvidenceWindow(root,self.database,'case',self.root/'data/evidence'); window.withdraw()
        try:
            self.assertIsNone(window.photo)
            window.table.selection_set(evidence_id)
            window.preview()
            self.assertIsNotNone(window.photo)
            self.assertIn('PNG',window.metadata.get())
            window.clear(); self.assertIsNone(window.photo)
        finally:
            window.destroy(); root.destroy()


if __name__=='__main__': unittest.main()
