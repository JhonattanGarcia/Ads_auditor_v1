import json
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import patch

from brand_threat_monitor.ui.app import Application
from brand_threat_monitor.storage.database import connect, initialize


class DesktopTests(unittest.TestCase):
    def setUp(self):
        """Create isolated test fixtures and resources before each scenario."""
        self.tmp=tempfile.TemporaryDirectory(); self.workspace=Path(self.tmp.name)
        self.root=tk.Tk(); self.root.withdraw()
        self.app=Application(self.root,self.workspace)

    def tearDown(self):
        """Close test resources and remove temporary files after each scenario."""
        self.app.close(); self.tmp.cleanup()

    def test_load_manifest_does_not_query_source(self):
        """Verify that load manifest does not query source."""
        project=Path(__file__).resolve().parents[2]
        with patch('brand_threat_monitor.ui.app.collect') as collect:
            self.app.load_path(project/'profiles/searches.json')
            self.assertEqual(len(self.app.profile_table.get_children()),1)
            self.assertEqual(self.app.plan.profiles[0]['client_id'],'sample')
            collect.assert_not_called()

    def test_days_override_profile_without_requesting_identity(self):
        """Verify that days override profile without requesting identity."""
        from brand_threat_monitor.config.profiles import SearchPlan, load_profile
        project=Path(__file__).resolve().parents[2]
        profile=load_profile(project/'profiles/example.json')
        self.app.plan=SearchPlan([profile],self.workspace/'results')
        self.app.search_rows.from_profiles([profile])
        self.assertEqual(self.app.days.get(),'1')
        self.app.days.set('7')
        lists=self.workspace/'lists'; lists.mkdir()
        for p in (project/'lists').glob('*.json'):
            (lists/p.name).write_bytes(p.read_bytes())
        with patch('brand_threat_monitor.ui.app.threading.Thread') as worker, patch('brand_threat_monitor.ui.app.messagebox.showerror', side_effect=AssertionError):
            self.app.start()
            queries,output,actor,snapshot,limits=worker.call_args.kwargs['args']
            self.assertEqual(queries[0]['days_to_review'],7)
            self.assertEqual(queries[0]['search']['date_range'],{'mode':'rolling_days'})
            self.assertEqual(actor,'local_operator')
            self.assertEqual(profile['days_to_review'],1)
        self.app.busy=False
        self.app.set_busy(False)

    def test_manual_execution_skips_disabled_brazil_row(self):
        """Verify that manual execution skips disabled brazil row."""
        self.app.search_rows.add('CO','pichincha',True)
        self.app.search_rows.add('BR','bradesco',False)
        self.app.render_searches()
        self.assertEqual(len(self.app.profile_table.get_children()),2)
        lists=self.workspace/'lists'; lists.mkdir()
        project=Path(__file__).resolve().parents[2]
        for p in (project/'lists').glob('*.json'):
            (lists/p.name).write_bytes(p.read_bytes())
        with patch('brand_threat_monitor.ui.app.threading.Thread') as worker, patch('brand_threat_monitor.ui.app.messagebox.showerror',side_effect=AssertionError):
            self.app.start()
            queries=worker.call_args.kwargs['args'][0]
            self.assertEqual(len(queries),1)
            self.assertEqual(queries[0]['country'],'co')
            self.assertEqual(queries[0]['criteria'][0]['query'],'pichincha')
        self.app.busy=False; self.app.set_busy(False)

    def test_enabled_checkbox_applies_immediately_and_autosaves(self):
        """Verify that enabled checkbox applies immediately and autosaves."""
        row_id=self.app.search_rows.add('CO','pichincha',True)
        self.app.render_searches()
        self.app.profile_table.selection_set(row_id)
        self.app.select_search()
        self.app.enabled_button.invoke()
        self.assertFalse(self.app.search_rows.get(row_id)['enabled'])
        saved=json.loads((self.workspace/'data/search_list.json').read_text())
        self.assertFalse(saved['profiles'][0]['enabled'])
        self.assertEqual(self.app.search_rows.queries(1),[])

    def test_manual_rows_and_days_restore_when_reopening(self):
        """Verify that manual rows and days restore when reopening."""
        self.app.search_rows.add('CO','pichincha',True)
        self.app.search_rows.add('BR','bradesco',False)
        self.app.render_searches()
        self.app.days.set('3')
        self.app.close()
        self.root=tk.Tk(); self.root.withdraw()
        self.app=Application(self.root,self.workspace)
        self.assertEqual(len(self.app.search_rows.rows),2)
        self.assertTrue(self.app.search_rows.rows[0]['enabled'])
        self.assertFalse(self.app.search_rows.rows[1]['enabled'])
        self.assertEqual(self.app.days.get(),'3')
        self.assertEqual(self.app.search_rows.queries(3)[0]['country'],'co')

    def test_saved_results_load_on_reopen_with_newest_first(self):
        """Verify that saved results load on reopen with newest first."""
        from brand_threat_monitor.storage.repositories import import_result
        lists=self.workspace/'lists'; lists.mkdir()
        project=Path(__file__).resolve().parents[2]
        for p in (project/'lists').glob('*.json'):
            (lists/p.name).write_bytes(p.read_bytes())
        with connect(self.app.database) as db:
            initialize(db)
            for run,ad,stamp in [('old','ad-old','2026-11-15T12:00:00+00:00'),('new','ad-new','2026-11-17T12:00:00+00:00')]:
                import_result(db,{'schema_version':'1.0','run_id':run,'source':'fixture','started_at':stamp,
                    'status':'partial','coverage':'partial','country':'CO','query':'test',
                    'ads':[{'source':'fixture','ad_id':ad,'body':ad}],
                    'observations':[{'source':'fixture','ad_id':ad,'run_id':run,'observed_at':stamp}]},actor='tester')
        self.app.close(); self.root=tk.Tk(); self.root.withdraw()
        with patch('brand_threat_monitor.ui.app.collect') as collector:
            self.app=Application(self.root,self.workspace)
            self.assertEqual(len(self.app.rows),2)
            self.assertEqual(self.app.selected['ad_id'],'ad-new')
            collector.assert_not_called()
        self.app.tabs.select(self.app.audit); self.root.update()
        self.assertEqual(self.app.selected['ad_id'],'ad-new')

    def test_review_footer_and_detail_fit_minimum_window(self):
        """Verify that review footer and detail fit minimum window."""
        self.root.geometry('850x600')
        self.app.tabs.select(self.app.audit)
        self.root.deiconify(); self.root.update()
        self.assertGreaterEqual(self.app.detail.winfo_height(),40)
        self.assertLessEqual(self.app.review_notice.winfo_y()+self.app.review_notice.winfo_height(),self.app.audit.winfo_height())
        self.assertTrue(all(button.winfo_ismapped() for button in self.app.decision_buttons))
        self.root.withdraw()

    def test_queue_selection_displays_payload_without_opening_url(self):
        """Verify that queue selection displays payload without opening url."""
        lists=self.workspace/'lists'; lists.mkdir()
        project=Path(__file__).resolve().parents[2]
        for p in (project/'lists').glob('*.json'):
            (lists/p.name).write_bytes(p.read_bytes())
        with connect(self.app.database) as db:
            initialize(db)
            with db:
                db.execute("INSERT INTO ads VALUES ('fixture','ad1',NULL,'2026-11-15','2026-11-15','2026-11-15',?)",(json.dumps({'body':'Contenido ficticio'}),))
                db.execute("INSERT INTO runs VALUES ('r','2026-11-15',NULL,'partial','fixture','1','partial','{}')")
                db.execute("INSERT INTO run_queries VALUES ('q','r',NULL,'CO','test',NULL,NULL)")
                db.execute("INSERT INTO ad_observations VALUES ('r','fixture','ad1','2026-11-15')")
                db.execute("INSERT INTO observation_queries VALUES ('r','fixture','ad1','q')")
        with patch('brand_threat_monitor.ui.app.webbrowser.open') as browser:
            self.app.refresh()
            self.assertEqual(len(self.app.rows),1)
            self.app.queue_table.selection_set('0')
            self.app.show_selected()
            self.assertIn('Contenido ficticio',self.app.detail.get('1.0','end'))
            browser.assert_not_called()

    def test_classification_does_not_request_confirmation(self):
        """Verify that classification does not request confirmation."""
        from contextlib import nullcontext
        row={'source':'fixture','ad_id':'123','advertiser_id':'456','client_id':None,'state':'pending_review','case_id':'case1'}
        for decision in ('spam','attack','pending'):
            self.app.selected=row
            with patch('brand_threat_monitor.ui.app.messagebox.askyesno',side_effect=AssertionError('Unexpected confirmation')), \
                 patch('brand_threat_monitor.ui.app.filedialog.askopenfilename',return_value='evidence.png'), \
                 patch('brand_threat_monitor.ui.app.connect',return_value=nullcontext(object())), \
                 patch('brand_threat_monitor.ui.app.initialize'), \
                 patch('brand_threat_monitor.ui.app.load_lists'), \
                 patch('brand_threat_monitor.ui.app.merge_database_lists'), \
                 patch('brand_threat_monitor.ui.app.decide') as decide, \
                 patch.object(self.app,'refresh'):
                self.app.classify(decision)
                self.assertEqual(decide.call_args.args[2],decision)
                self.assertEqual(decide.call_args.kwargs['actor'],'local_operator')

    def test_repeat_validation_and_stop(self):
        """Verify that repeat validation and stop."""
        import time
        self.app.repeat_hours.set('1')
        self.app.repeat_enabled.set(True)
        self.app.repeat_changed()
        self.assertAlmostEqual(self.app.repeat_due-time.monotonic(),3600,delta=2)
        self.app.stop_searches()
        self.assertIsNone(self.app.repeat_due)
        self.assertFalse(self.app.repeat_enabled.get())
        for hours in (0,0.5,0.99,float('nan'),float('inf'),True,8761):
            with self.assertRaises(ValueError):
                self.app.validate_repeat({'enabled':True,'hours':hours})

    def test_repeat_settings_restore_and_busy_batch_does_not_overlap(self):
        """Verify that repeat settings restore and busy batch does not overlap."""
        self.app.repeat_hours.set('2')
        self.app.repeat_enabled.set(True); self.app.repeat_changed()
        saved=self.app.search_list_file
        document=json.loads(saved.read_text(encoding='utf-8'))
        self.assertEqual(document['repeat'],{'enabled':True,'hours':2.0})
        self.app.repeat_enabled.set(False)
        self.app.load_path(saved)
        self.assertTrue(self.app.repeat_enabled.get())
        self.assertIsNotNone(self.app.repeat_due)
        self.app.busy=True
        self.app.schedule_repeat()
        self.assertIsNone(self.app.repeat_due)
        self.app.busy=False
        self.app.schedule_repeat()
        self.assertIsNotNone(self.app.repeat_due)

    def test_due_repeat_starts_once(self):
        """Verify that due repeat starts once."""
        import time
        self.app.repeat_due=time.monotonic()-1
        self.app.after_cancel(self.app.timer)
        with patch.object(self.app,'start',side_effect=lambda:setattr(self.app,'busy',True)) as start:
            self.app.poll()
            self.assertEqual(start.call_count,1)
            self.assertIsNone(self.app.repeat_due)
        self.app.busy=False

    def test_repeat_runs_at_frequency_and_rearms_after_batch_completion(self):
        """Verify that repeat runs at frequency and rearms after batch completion."""
        project=Path(__file__).resolve().parents[2]
        self.app.search_rows.add('CO','Sample',True)
        lists=self.workspace/'lists'; lists.mkdir()
        for file in (project/'lists').glob('*.json'):
            (lists/file.name).write_bytes(file.read_bytes())
        self.app.repeat_hours.set('1')
        self.app.repeat_enabled.set(True)
        self.app.after_cancel(self.app.timer)
        def poll_at(stamp):
            """Poll scheduled UI work under a simulated monotonic clock without a real-time wait."""
            with patch('brand_threat_monitor.ui.app.time.monotonic',return_value=stamp):
                self.app.poll()
            self.app.after_cancel(self.app.timer)
        try:
            with patch('brand_threat_monitor.ui.app.time.monotonic',return_value=100):
                self.app.repeat_changed()
            self.assertEqual(self.app.repeat_due,3700)
            with patch('brand_threat_monitor.ui.app.threading.Thread') as worker, patch.object(self.app,'refresh'):
                poll_at(3699)
                worker.assert_not_called()
                poll_at(3700)
                self.assertEqual(worker.call_count,1)
                self.assertTrue(self.app.busy)
                poll_at(7300)
                self.assertEqual(worker.call_count,1)
                self.app.events.put(('done',None))
                poll_at(7400)
                self.assertEqual(self.app.repeat_due,11000)
                self.assertIn('Next run:',self.app.status.get())
                poll_at(10999)
                self.assertEqual(worker.call_count,1)
                poll_at(11000)
                self.assertEqual(worker.call_count,2)
                queries,output,actor,snapshot,limits=worker.call_args.kwargs['args']
                self.assertEqual(queries[0]['criteria'][0]['query'],'Sample')
                self.assertEqual(limits['max_pages'],20)
        finally:
            self.app.busy=False
            self.app.set_busy(False)
            self.app.timer=self.app.after(150,self.app.poll)

    def prepare_result_import(self):
        """Create list configuration and a valid result file without querying Meta."""
        from test_database import sample
        lists=self.workspace/'lists'; lists.mkdir(exist_ok=True)
        project=Path(__file__).resolve().parents[2]
        for path in (project/'lists').glob('*.json'):
            (lists/path.name).write_bytes(path.read_bytes())
        document=sample()
        document['ads'][0]['body']='Imported ad copy'
        path=self.workspace/'results.json'
        path.write_text(json.dumps(document),encoding='utf-8')
        return path,document

    def test_manual_results_import_displays_ad_and_is_idempotent(self):
        """Import a transferred result into the queue without fetching or duplicating source data."""
        path,document=self.prepare_result_import()
        self.app.queue_filters.values['country'].set('BR')
        with patch('brand_threat_monitor.ui.app.collect') as collect:
            first=self.app.load_results_path(path)
            second=self.app.load_results_path(path)
            collect.assert_not_called()
        self.assertTrue(first['imported']); self.assertFalse(second['imported'])
        self.assertEqual(self.app.selected['ad_id'],'ad1')
        self.assertIn('Imported ad copy',self.app.detail.get('1.0','end'))
        self.assertEqual(self.app.queue_filters.values['country'].get(),'')
        with connect(self.app.database) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM runs').fetchone()[0],1)
            self.assertEqual(db.execute('SELECT count(*) FROM audit_log').fetchone()[0],1)

    def test_manual_results_import_rejects_summary_and_rolls_back_invalid_ad(self):
        """Reject wrong document types and preserve an empty database after invalid import."""
        path,document=self.prepare_result_import()
        summary=self.workspace/'run_summary.json'; summary.write_text('{}',encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'collector results.json'):
            self.app.load_results_path(summary)
        document['observations']=[]
        path.write_text(json.dumps(document),encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'Invalid results content'): self.app.load_results_path(path)
        with connect(self.app.database) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM runs').fetchone()[0],0)

    def test_manual_results_import_keeps_review_decisions(self):
        """Reimporting results must not return classified ads to the review queue."""
        from brand_threat_monitor.review.service import open_case,decide
        path,document=self.prepare_result_import()
        self.app.load_results_path(path)
        with connect(self.app.database) as db:
            case=open_case(db,'fixture','ad1',actor='tester')
            decide(db,case['case_id'],'spam',actor='tester',reason='Fixture decision',confirm_id='ad1')
        self.app.load_results_path(path)
        self.assertEqual(self.app.rows,[])
        self.assertIn('Imported search results',self.app.analysis_information)

    def test_manual_results_picker_cancel_and_busy_guard(self):
        """Cancelling the picker changes nothing and imports are blocked during collection."""
        with patch('brand_threat_monitor.ui.app.filedialog.askopenfilename',return_value=''), patch.object(self.app,'load_results_path') as imported:
            self.app.load_results()
            imported.assert_not_called()
        self.app.busy=True
        try:
            with self.assertRaisesRegex(ValueError,'Wait for the search'):
                self.app.load_results()
        finally: self.app.busy=False

    def test_review_link_box_tracks_selection_and_exports_external_urls(self):
        """Selected-ad links remain visible below the queue and export through the review action."""
        path,document=self.prepare_result_import()
        document['ads'][0]['body']='Visit https://example.com/offer'
        path.write_text(json.dumps(document),encoding='utf-8')
        self.app.load_results_path(path)
        self.assertIn('External destination: https://example.com/offer',self.app.links_text.get('1.0','end'))
        with patch('brand_threat_monitor.ui.app.webbrowser.open') as browser:
            self.app.copy_external_links()
            self.assertEqual(self.app.clipboard_get(),'https://example.com/offer')
            target=self.workspace/'external.txt'
            with patch('brand_threat_monitor.ui.app.filedialog.asksaveasfilename',return_value=str(target)):
                self.app.export_links()
            self.assertEqual(target.read_text(encoding='utf-8'),'https://example.com/offer\n')
            browser.assert_not_called()
        self.app.set_detail('No selection')
        self.assertEqual(self.app.selected_external_links,[])
        self.assertNotIn('https://example.com/offer',self.app.links_text.get('1.0','end'))


if __name__=='__main__': unittest.main()
