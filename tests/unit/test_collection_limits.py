import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import Mock
from brand_threat_monitor.config.limits import validate_limits,DEFAULT_LIMITS
from brand_threat_monitor.collectors.meta import MetaCollector
from brand_threat_monitor.ui.app import Application


class CollectionLimitTests(unittest.TestCase):
    def test_validation(self):
        """Verify that validation."""
        self.assertEqual(validate_limits({}),DEFAULT_LIMITS)
        for key in DEFAULT_LIMITS:
            for value in (0,-1,True,'10',1000000):
                with self.subTest(key=key,value=value):
                    with self.assertRaises(ValueError): validate_limits({key:value})

    def test_page_limit_stops_cursor_without_fetching_extra_page(self):
        """Verify that page limit stops cursor without fetching extra page."""
        collector=MetaCollector.__new__(MetaCollector)
        collector.max_pages=2
        backend=Mock(); backend.stats={'pages_fetched':0}
        original=Mock(return_value=({'ads':[]},'next'))
        backend.client.search_ads=original
        def search(**kwargs):
            """Yield scripted fixture results or failures without contacting the live source."""
            cursor=None
            while True:
                response,cursor=backend.client.search_ads(cursor=cursor)
                backend.stats['pages_fetched']+=1
                if not cursor: return
            yield
        backend.search=search
        collector._backend=backend
        self.assertEqual(list(collector.search(query='test',country='CO',max_results=100)),[])
        self.assertEqual(original.call_count,2)
        self.assertEqual(backend.stats['pages_fetched'],2)
        self.assertTrue(backend.stats['page_limit_reached'])
        self.assertIs(backend.client.search_ads,original)

    def test_ui_limits_are_saved_and_restored(self):
        """Verify that ui limits are saved and restored."""
        with tempfile.TemporaryDirectory() as directory:
            root=tk.Tk(); root.withdraw()
            app=Application(root,Path(directory))
            try:
                expected={'max_scan':250,'max_pages':3,'max_duration':60,'idle_timeout':15}
                for key,value in expected.items(): app.limit_values[key].set(str(value))
                saved=app.search_list_file
                for key in expected: app.limit_values[key].set(str(DEFAULT_LIMITS[key]))
                # Save a separate document to avoid autosave replacing the fixture.
                document=app.search_list_document(); document['collection_limits']=expected
                import json
                fixture=Path(directory)/'saved.json'; fixture.write_text(json.dumps(document),encoding='utf-8')
                app.load_path(fixture)
                self.assertEqual(app.collection_limits(),expected)
                self.assertEqual(json.loads(saved.read_text(encoding='utf-8'))['collection_limits'],expected)
            finally: app.close()

    def test_result_and_summary_record_limits_and_page_stop(self):
        """Verify that result and summary record limits and page stop."""
        import json
        from brand_threat_monitor.ingestion.collector import collect
        from brand_threat_monitor.ingestion.service import persist_result
        from unittest.mock import patch
        profile=json.loads((Path(__file__).resolve().parents[2]/'profiles/example.json').read_text(encoding='utf-8-sig'))
        options={}
        class Fake:
            def __init__(self,**kwargs):
                """Initialize the controlled fake resource and its test counters."""
                options.update(kwargs)
                self.max_duration=kwargs['max_duration']; self.idle_timeout=kwargs['idle_timeout']; self.max_pages=kwargs['max_pages']
                self.stats={'pages_fetched':2,'page_limit_reached':True,'errors':0}
            def __enter__(self):
                """Return the controlled fixture resource for the test context manager."""
                return self
            def __exit__(self,*args):
                """Leave the fixture context without suppressing test failures."""
                pass
            def search(self,**kwargs):
                """Yield scripted fixture results or failures without contacting the live source."""
                return iter(())
        result=collect(profile,collector_factory=Fake,max_scan=250,max_pages=2,max_duration=180,idle_timeout=20)
        self.assertEqual(result['stop_reason'],'page_limit_reached')
        self.assertEqual(result['errors'],[])
        self.assertEqual(options['max_pages'],2)
        with tempfile.TemporaryDirectory() as directory:
            summary,_=persist_result(result,Path(directory)/'results.json',Path(directory)/'db.sqlite3',actor='tester')
            self.assertEqual(summary['search_limits'],{'max_duration_seconds':180,'idle_timeout_seconds':20,'max_pages':2,'max_scanned_ads':250})
            self.assertEqual(summary['connector_stats']['pages_fetched'],2)

    def test_legacy_search_list_restores_default_limits_without_intermediate_saves(self):
        """Verify that legacy search list restores default limits without intermediate saves."""
        import json
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as directory:
            root=tk.Tk(); root.withdraw(); app=Application(root,Path(directory))
            try:
                document=app.search_list_document(); document.pop('collection_limits')
                fixture=Path(directory)/'legacy.json'; fixture.write_text(json.dumps(document),encoding='utf-8')
                app.limit_values['max_pages'].set('3')
                with patch('brand_threat_monitor.ui.app.write_json',wraps=__import__('brand_threat_monitor.ingestion.service',fromlist=['write_json']).write_json) as saved:
                    app.load_path(fixture)
                self.assertEqual(app.collection_limits(),DEFAULT_LIMITS)
                self.assertEqual(saved.call_count,1)
            finally: app.close()

    def test_incomplete_limit_edit_does_not_show_error_when_days_change(self):
        """Verify that incomplete limit edit does not show error when days change."""
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as directory:
            root=tk.Tk(); root.withdraw(); app=Application(root,Path(directory))
            try:
                with patch('brand_threat_monitor.ui.app.messagebox.showerror') as error:
                    app.limit_values['max_scan'].set('')
                    app.days.set('2')
                    error.assert_not_called()
                with self.assertRaisesRegex(ValueError,'whole number'): app.collection_limits()
            finally: app.close()
