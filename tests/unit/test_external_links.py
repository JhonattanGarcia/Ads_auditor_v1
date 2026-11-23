"""URL extraction and explicit exports never fetch external destinations."""
import csv
import io
import json
import tempfile
import unittest
from pathlib import Path
from test_database import sample
from brand_threat_monitor.storage.database import connect,initialize
from brand_threat_monitor.storage.repositories import import_result
from brand_threat_monitor.search.links import associated_links
from brand_threat_monitor.exports.links import external_link_rows,export_external_links


class ExternalLinkTests(unittest.TestCase):
    def setUp(self):
        """Create an isolated ad with destination, body and media URLs."""
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.context=connect(self.root/'db.sqlite3');self.db=self.context.__enter__();initialize(self.db)
        result=sample()
        result['ads'][0].update(body='Visit https://example.com/offer and https://other.example/path.',
            creatives=[{'link_url':'https://example.com/offer','image_url':'https://cdn.example/image.jpg'}],
            page={'page_url':'https://www.facebook.com/sample'})
        import_result(self.db,result,actor='tester')
        self.rows=[{'source':'fixture','ad_id':'ad1','client_id':None}]

    def tearDown(self):
        """Close SQLite and remove only test fixture files."""
        self.context.__exit__(None,None,None);self.temp.cleanup()

    def test_associated_links_prioritize_destinations_and_keep_media_separate(self):
        """Media and platform references remain visible but do not become external destinations."""
        payload=json.loads(self.db.execute('SELECT payload_json FROM ads').fetchone()[0])
        links=associated_links(payload)
        self.assertEqual(links[0]['kind'],'External destination')
        self.assertEqual(len([r for r in links if r['kind']=='External destination']),2)
        self.assertIn({'kind':'Media','url':'https://cdn.example/image.jpg'},links)
        self.assertTrue(any(r['kind']=='Publisher profile' for r in links))

    def test_csv_exports_context_and_deduplicates_rows_without_audit_changes(self):
        """CSV preserves ad context and excludes media/platform URLs without changing review data."""
        count=self.db.execute('SELECT count(*) FROM audit_log').fetchone()[0]
        target=self.root/'links.csv'
        result=export_external_links(self.db,self.rows*2,target)
        rows=list(csv.DictReader(io.StringIO(target.read_text(encoding='utf-8-sig'))))
        self.assertEqual(result['rows'],2);self.assertEqual(len(rows),2)
        self.assertEqual(rows[0]['ad_id'],'ad1')
        self.assertEqual({r['url'] for r in rows},{'https://example.com/offer','https://other.example/path'})
        self.assertEqual(self.db.execute('SELECT count(*) FROM audit_log').fetchone()[0],count)

    def test_txt_export_and_no_overwrite(self):
        """Text export is one URL per line and existing exports are preserved."""
        target=self.root/'links.txt';export_external_links(self.db,self.rows,target)
        before=target.read_bytes()
        self.assertEqual(len(target.read_text(encoding='utf-8').splitlines()),2)
        with self.assertRaises(FileExistsError):export_external_links(self.db,self.rows,target)
        self.assertEqual(target.read_bytes(),before)

    def test_meta_redirect_and_missing_creatives(self):
        """Unwrap external targets without visiting them and handle absent creative arrays."""
        links=associated_links({'creatives':None,'link_url':'https://l.facebook.com/l.php?u=https%3A%2F%2Fexample.com%2Foffer'})
        self.assertEqual(links,[{'kind':'External destination','url':'https://example.com/offer'}])

    def test_no_destinations_does_not_create_empty_file(self):
        """No-match exports fail clearly instead of publishing misleading empty artifacts."""
        target=self.root/'empty.txt'
        with self.assertRaisesRegex(ValueError,'No external links'):
            export_external_links(self.db,[],target)
        self.assertFalse(target.exists())
