import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from brand_threat_monitor.ingestion.service import persist_result
from brand_threat_monitor.storage.database import connect


def result(run_id='test-run'):
    """Build the controlled result fixture used by this test scenario."""
    return {'schema_version':'1.0','run_id':run_id,'source':'fixture','source_version':'1',
            'started_at':'2026-11-15T12:00:00+00:00','finished_at':'2026-11-15T12:01:00+00:00',
            'status':'partial','coverage':'partial','country':'CO','query':'marca',
            'client_id':'client1','client_name':'Marca','scanned_ads':1,'excluded_by_date':0,
            'ads':[{'source':'fixture','ad_id':'ad1','advertiser_id':'page1'}],
            'observations':[{'run_id':run_id,'source':'fixture','ad_id':'ad1','observed_at':'2026-11-15T12:00:00+00:00'}],
            'errors':[],'warnings':[]}


class PersistenceTests(unittest.TestCase):
    def test_save_reimport_and_second_run(self):
        """Verify that save reimport and second run."""
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            for run_id,expected in [('run1',1),('run1',None),('run2',0)]:
                summary,path=persist_result(result(run_id),root/run_id/'results.json',root/'db.sqlite3',actor='tester')
                self.assertEqual(summary['persistence']['status'],'saved')
                self.assertEqual(summary['counts']['new_ads'],expected)
                self.assertEqual(path.name,'run_summary.json')
                self.assertEqual(json.loads(path.read_text())['run_id'],run_id)
            with connect(root/'db.sqlite3') as db:
                self.assertEqual(db.execute('SELECT count(*) FROM ads').fetchone()[0],1)
                self.assertEqual(db.execute('SELECT count(*) FROM ad_observations').fetchone()[0],2)
                self.assertEqual(db.execute('SELECT client_id FROM run_queries LIMIT 1').fetchone()[0],'client1')

    def test_storage_error_preserves_json_for_recovery(self):
        """Verify that storage error preserves json for recovery."""
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            with patch('brand_threat_monitor.ingestion.service.import_result',side_effect=RuntimeError('disk failure')):
                summary,path=persist_result(result(),root/'results.json',root/'db.sqlite3',actor='tester')
            self.assertEqual(summary['persistence']['status'],'failed')
            self.assertEqual(json.loads((root/'results.json').read_text())['ads'][0]['ad_id'],'ad1')
            self.assertEqual(summary['errors'][-1]['stage'],'persistence')

    def test_cancelled_and_failed_source_runs_are_saved(self):
        """Verify that cancelled and failed source runs are saved."""
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            for status in ['cancelled','failed']:
                data=result(status)
                data.update(status=status,ads=[],observations=[])
                data['errors']=[{'type':'CollectorError','message':'network'}]
                summary,_=persist_result(data,root/status/'results.json',root/'db.sqlite3',actor='tester')
                self.assertEqual(summary['status'],status)
                self.assertEqual(summary['persistence']['status'],'saved')
                self.assertEqual(len(summary['errors']),1)


if __name__=='__main__': unittest.main()
