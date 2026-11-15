import copy
import json
import tempfile
import unittest
from pathlib import Path
from brand_threat_monitor.lists.service import load_lists, validate_document, evaluate
from brand_threat_monitor.review.queue import evaluate_result


def entry(key, value, scope=None):
    return {'source':'fixture',key:value,'scope':scope or {'type':'global'},
            'reason':'Prueba ficticia','reviewer':'tester','created_at':'2026-11-15T12:00:00+00:00',
            'active':True,'case_id':'fake-case','evidence_refs':['fake-evidence']}


def documents():
    return {kind:{'schema_version':'1.0','list_type':kind,'identity_fields':['source',key],'entries':[]}
            for kind,key in [('whitelist','advertiser_id'),('blacklist','advertiser_id'),('brownlist','ad_id')]}


class ListTests(unittest.TestCase):
    def snapshot(self, docs):
        with tempfile.TemporaryDirectory() as folder:
            for kind,doc in docs.items():
                (Path(folder)/(kind+'.json')).write_text(json.dumps(doc))
            return load_lists(folder)

    def ad(self, ad_id='ad1', advertiser='page1'):
        return {'source':'fixture','ad_id':ad_id,'advertiser_id':advertiser}

    def test_black_overrides_brown(self):
        docs=documents()
        docs['blacklist']['entries']=[entry('advertiser_id','page1')]
        docs['brownlist']['entries']=[entry('ad_id','ad1')]
        decision=evaluate(self.ad(),'client1',self.snapshot(docs))
        self.assertEqual(decision['state'],'known_black')
        self.assertEqual(decision['priority'],1)

    def test_white_retains_decision_but_not_queue(self):
        docs=documents()
        docs['whitelist']['entries']=[entry('advertiser_id','page1',{'type':'client','client_id':'client1'})]
        snapshot=self.snapshot(docs)
        result=evaluate_result({'run_id':'r','client_id':'client1','ads':[self.ad()]},snapshot)
        self.assertEqual(len(result['decisions']),1)
        self.assertEqual(result['queue'],[])
        self.assertEqual(evaluate(self.ad(),'client2',snapshot)['state'],'pending_review')

    def test_brown_applies_only_to_one_ad_and_source(self):
        docs=documents()
        docs['brownlist']['entries']=[entry('ad_id','ad1')]
        snapshot=self.snapshot(docs)
        self.assertEqual(evaluate(self.ad(),'c',snapshot)['state'],'discarded_brown')
        self.assertEqual(evaluate(self.ad('ad2'),'c',snapshot)['state'],'pending_review')
        ad=self.ad(); ad['source']='another'
        self.assertEqual(evaluate(ad,'c',snapshot)['state'],'pending_review')

    def test_conflict_across_overlapping_scopes(self):
        docs=documents()
        docs['whitelist']['entries']=[entry('advertiser_id','page1',{'type':'client','client_id':'client1'})]
        docs['blacklist']['entries']=[entry('advertiser_id','page1')]
        snapshot=self.snapshot(docs)
        self.assertEqual(evaluate(self.ad(),'client1',snapshot)['state'],'list_conflict')
        self.assertEqual(evaluate(self.ad(),'client2',snapshot)['state'],'known_black')

    def test_duplicate_and_missing_evidence_rejected(self):
        docs=documents()
        doc=docs['blacklist']
        doc['entries']=[entry('advertiser_id','page1')]
        doc['entries'][0]['evidence_refs']=[]
        with self.assertRaises(ValueError): validate_document(doc,'blacklist')
        doc['entries']=[entry('advertiser_id','page1')]*2
        with self.assertRaises(ValueError): validate_document(doc,'blacklist')

    def test_inactive_entries_do_not_apply(self):
        docs=documents()
        item=entry('advertiser_id','page1'); item['active']=False
        docs['blacklist']['entries']=[item]
        self.assertEqual(evaluate(self.ad(),'c',self.snapshot(docs))['state'],'pending_review')


if __name__=='__main__': unittest.main()
