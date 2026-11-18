import csv
import json
import tempfile
import unittest
from pathlib import Path
from brand_threat_monitor.storage.database import connect,initialize
from brand_threat_monitor.storage.repositories import import_result
from brand_threat_monitor.review.service import open_case,decide
from brand_threat_monitor.exports.service import export_case,build_case_file,csv_safe


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name)
        self.ctx=connect(self.root/'db.sqlite3'); self.db=self.ctx.__enter__(); initialize(self.db)
        data={'schema_version':'1.0','run_id':'run','source':'fixture','started_at':'2026-11-15T12:00:00+00:00',
              'status':'partial','coverage':'partial','country':'CO','query':'=HYPERLINK("danger")',
              'ads':[{'source':'fixture','ad_id':'ad','advertiser_id':'page','body':'Original text'}],
              'observations':[{'source':'fixture','ad_id':'ad','run_id':'run','observed_at':'2026-11-15T12:00:00+00:00'}]}
        import_result(self.db,data,actor='tester')
        self.case=open_case(self.db,'fixture','ad',actor='tester')['case_id']
        decide(self.db,self.case,'pending',actor='tester',reason='Missing details')

    def tearDown(self):
        self.ctx.__exit__(None,None,None); self.tmp.cleanup()

    def test_json_preserves_case_content_query_and_history(self):
        path=export_case(self.db,self.case,self.root/'case.json',format='json')
        doc=json.loads(path.read_text())
        self.assertEqual(doc['ad']['content']['body'],'Original text')
        self.assertEqual(doc['observations'][0]['query'],'=HYPERLINK("danger")')
        self.assertEqual(doc['case']['decision'],'pending')
        self.assertEqual(len(doc['events']),2)
        self.assertIn('after',doc['events'][1])
        self.assertFalse(self.db.in_transaction)

    def test_csv_is_parseable_and_protects_untrusted_cells(self):
        path=export_case(self.db,self.case,self.root/'case.csv',format='csv')
        with path.open(encoding='utf-8-sig',newline='') as stream: rows=list(csv.DictReader(stream))
        query=next(row['value'] for row in rows if row['section']=='observations' and row['field']=='query')
        self.assertTrue(query.startswith("'="))
        self.assertTrue(any(row['section']=='events' for row in rows))

    def test_formula_prefixes_and_normal_text(self):
        for value in ['=1+1',' +SUM(A1)','-2','@test','\t=1','\n=1']:
            self.assertTrue(csv_safe(value).startswith("'"))
        self.assertEqual(csv_safe('ordinary text'),'ordinary text')

    def test_existing_file_is_not_overwritten(self):
        path=self.root/'existing.json'; path.write_text('keep')
        with self.assertRaises(ValueError): export_case(self.db,self.case,path,format='json')
        self.assertEqual(path.read_text(),'keep')

    def test_unknown_case_leaves_no_file(self):
        path=self.root/'unknown.json'
        with self.assertRaises(ValueError): export_case(self.db,'unknown',path,format='json')
        self.assertFalse(path.exists())
        self.assertFalse(self.db.in_transaction)


if __name__=='__main__': unittest.main()
