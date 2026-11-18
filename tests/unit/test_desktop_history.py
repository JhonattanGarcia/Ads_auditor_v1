import json
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import patch

from brand_threat_monitor.ui.history import HistoryWindow
from brand_threat_monitor.ui.audit import format_ad
from brand_threat_monitor.storage.database import connect, initialize
from brand_threat_monitor.review.service import open_case, decide, case_detail


class HistoryDesktopTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.database=Path(self.tmp.name)/'db.sqlite3'
        with connect(self.database) as db:
            initialize(db)
            with db:
                db.execute("INSERT INTO ads VALUES ('fixture','synthetic',NULL,'2026-11-15','2026-11-15','2026-11-15','{}')")
                db.execute("INSERT INTO runs VALUES ('run','2026-11-15',NULL,'partial','fixture','1','partial',?)",(json.dumps({'query':'synthetic','ads':[],'coverage':'partial'}),))
            self.case_id=open_case(db,'fixture','synthetic',actor='tester')['case_id']
            decide(db,self.case_id,'spam',actor='tester',reason='Synthetic review',confirm_id='synthetic')
        self.root=tk.Tk(); self.root.withdraw()
        self.window=HistoryWindow(self.root,self.database)
        self.window.withdraw()

    def tearDown(self):
        self.window.destroy(); self.root.destroy(); self.tmp.cleanup()

    def test_history_shows_run_and_case_without_mutations(self):
        self.assertEqual(len(self.window.run_table.get_children()),1)
        self.window.run_table.selection_set('run'); self.window.show_run()
        self.assertIn('synthetic',self.window.run_detail.get('1.0','end'))
        self.window.case_table.selection_set(self.case_id); self.window.show_case()
        self.assertIn('review_spam',self.window.case_detail.get('1.0','end'))
        with connect(self.database) as db:
            self.assertEqual(case_detail(db,self.case_id)['case']['decision'],'spam')

    def test_correction_button_uses_transactional_service(self):
        self.window.case_table.selection_set(self.case_id); self.window.show_case()
        with patch('brand_threat_monitor.ui.history.simpledialog.askstring',return_value='Wrong classification'), patch('brand_threat_monitor.ui.history.messagebox.askyesno',return_value=True):
            self.window.correct()
        with connect(self.database) as db:
            detail=case_detail(db,self.case_id)
            self.assertIsNone(detail['case']['decision'])
            self.assertEqual(detail['events'][-1]['operation'],'correct_case')
            self.assertEqual(db.execute('SELECT active FROM brownlist').fetchone()[0],0)

    def test_history_exports_selected_case(self):
        self.window.case_table.selection_set(self.case_id); self.window.show_case()
        output=Path(self.tmp.name)/'case.json'
        with patch('brand_threat_monitor.ui.history.filedialog.asksaveasfilename',return_value=str(output)), patch('brand_threat_monitor.ui.history.messagebox.showinfo'):
            self.window.export('json')
        self.assertEqual(json.loads(output.read_text())['case']['case_id'],self.case_id)

    def test_history_filters_apply_to_both_tabs_and_can_be_cleared(self):
        self.window.filters.values['criterion'].set('does-not-exist')
        self.window.refresh()
        self.assertEqual(len(self.window.run_table.get_children()),0)
        self.assertEqual(len(self.window.case_table.get_children()),0)
        self.window.filters.values['criterion'].set('')
        self.window.refresh()
        self.assertEqual(len(self.window.run_table.get_children()),1)
        self.assertEqual(len(self.window.case_table.get_children()),1)

    def test_cancelled_correction_preserves_case(self):
        self.window.case_table.selection_set(self.case_id); self.window.show_case()
        with patch('brand_threat_monitor.ui.history.simpledialog.askstring',return_value=None):
            self.window.correct()
        with connect(self.database) as db:
            self.assertEqual(case_detail(db,self.case_id)['case']['decision'],'spam')


class AdPresentationTests(unittest.TestCase):
    def test_missing_content_is_explicit(self):
        self.assertIn('Not available',format_ad({}))

    def test_content_and_urls_are_displayed_passively(self):
        text=format_ad({'page':{'name':'Synthetic advertiser'},'creatives':[{'body':'Example text','link_url':'https://example.com','image_url':'https://example.com/image.png'}]})
        self.assertIn('Example text',text)
        self.assertIn('https://example.com',text)
        self.assertIn('Synthetic advertiser',text)


if __name__=='__main__': unittest.main()
