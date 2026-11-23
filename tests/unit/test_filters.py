import tempfile
import unittest
from pathlib import Path
from brand_threat_monitor.storage.database import connect,initialize
from brand_threat_monitor.storage.repositories import import_result
from brand_threat_monitor.review.service import open_case,list_cases
from brand_threat_monitor.review.queue import database_queue
from brand_threat_monitor.history.filters import Filters
from brand_threat_monitor.history.service import list_runs
from brand_threat_monitor.lists.service import load_lists


class FilterTests(unittest.TestCase):
    def setUp(self):
        """Create isolated test fixtures and resources before each scenario."""
        self.tmp=tempfile.TemporaryDirectory(); self.ctx=connect(Path(self.tmp.name)/'db')
        self.db=self.ctx.__enter__(); initialize(self.db)
        for run,client,country,query,stamp in [('run1','c1','CO','Pichincha','2026-11-15T02:00:00+00:00'),
                                              ('run2','c2','BR','Bradesco','2026-11-15T15:00:00+00:00')]:
            data={'schema_version':'1.0','run_id':run,'source':'fixture','started_at':stamp,
                  'status':'partial','coverage':'partial','country':country,'query':query,
                  'client_id':client,'client_name':client,
                  'ads':[{'source':'fixture','ad_id':'shared','advertiser_id':'page1'}],
                  'observations':[{'run_id':run,'source':'fixture','ad_id':'shared','observed_at':stamp}]}
            import_result(self.db,data,actor='tester')
        self.case=open_case(self.db,'fixture','shared',actor='tester',client_id='c1')['case_id']
        self.snapshot=load_lists(Path(__file__).resolve().parents[2]/'lists')

    def tearDown(self):
        """Close test resources and remove temporary files after each scenario."""
        self.ctx.__exit__(None,None,None); self.tmp.cleanup()

    def queue(self,filters):
        """Build the controlled queue fixture used by this test scenario."""
        return database_queue(self.db,self.snapshot,filters=filters)['queue']

    def test_country_and_criterion_use_same_observation(self):
        """Verify that country and criterion use same observation."""
        self.assertEqual(len(self.queue(Filters(country='co',criterion='CHIN'))),1)
        self.assertEqual(self.queue(Filters(country='CO',criterion='bradesco')),[])

    def test_exact_advertiser_id_and_literal_criterion(self):
        """Verify that exact advertiser id and literal criterion."""
        self.assertEqual(self.queue(Filters(advertiser_id='page')),[])
        self.assertEqual(len(self.queue(Filters(advertiser_id='page1'))),2)
        self.assertEqual(self.queue(Filters(criterion="%' OR 1=1 --")),[])

    def test_inclusive_local_day_and_run_dates(self):
        """Verify that inclusive local day and run dates."""
        filters=Filters(date_from='2026-11-14',date_to='2026-11-14')
        self.assertEqual(self.queue(filters)[0]['client_id'],'c1')
        self.assertEqual([r['run_id'] for r in list_runs(self.db,filters=filters)],['run1'])

    def test_case_context_does_not_leak_other_clients_observations(self):
        """Verify that case context does not leak other clients observations."""
        self.assertEqual(list_cases(self.db,filters=Filters(country='BR')),[])
        self.assertEqual(list_cases(self.db,filters=Filters(country='CO'))[0]['case_id'],self.case)

    def test_run_filters_and_empty_runs(self):
        """Verify that run filters and empty runs."""
        rows=list_runs(self.db,client_id='c2',filters=Filters(country='BR',advertiser_id='page1'))
        self.assertEqual([r['run_id'] for r in rows],['run2'])
        self.assertEqual(list_runs(self.db,filters=Filters(country='CO',criterion='bradesco')),[])

    def test_invalid_dates_and_country_rejected(self):
        """Verify that invalid dates and country rejected."""
        for kwargs in [{'country':'ZZ'},{'date_from':'2026-02-30'},
                       {'date_from':'2026-11-15','date_to':'2026-11-14'}, {'date_from':'20261115'}]:
            with self.subTest(kwargs=kwargs),self.assertRaises(ValueError): Filters(**kwargs)


if __name__=='__main__': unittest.main()
