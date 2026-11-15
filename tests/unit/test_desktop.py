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
        self.tmp=tempfile.TemporaryDirectory(); self.workspace=Path(self.tmp.name)
        self.root=tk.Tk(); self.root.withdraw()
        self.app=Application(self.root,self.workspace)

    def tearDown(self):
        self.app.close(); self.tmp.cleanup()

    def test_load_manifest_does_not_query_source(self):
        project=Path(__file__).resolve().parents[2]
        with patch('brand_threat_monitor.ui.app.collect') as collect:
            self.app.load_path(project/'profiles/searches.json')
            self.assertEqual(len(self.app.profile_table.get_children()),1)
            self.assertEqual(self.app.plan.profiles[0]['client_id'],'cliente_pichincha')
            collect.assert_not_called()

    def test_days_override_profile_without_requesting_identity(self):
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
            queries,output,actor,snapshot=worker.call_args.kwargs['args']
            self.assertEqual(queries[0]['days_to_review'],7)
            self.assertEqual(queries[0]['search']['date_range'],{'mode':'rolling_days'})
            self.assertEqual(actor,'local_operator')
            self.assertEqual(profile['days_to_review'],1)
        self.app.busy=False
        self.app.set_busy(False)

    def test_manual_execution_skips_disabled_brazil_row(self):
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

    def test_queue_selection_displays_payload_without_opening_url(self):
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


if __name__=='__main__': unittest.main()
