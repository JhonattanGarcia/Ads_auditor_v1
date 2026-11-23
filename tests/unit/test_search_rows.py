import unittest
from brand_threat_monitor.ui.search_rows import SearchRows
from brand_threat_monitor.search.query_builder import prepare
from urllib.parse import parse_qs,urlsplit


class SearchRowTests(unittest.TestCase):
    def test_only_enabled_country_and_criterion_are_executed(self):
        """Verify that only enabled country and criterion are executed."""
        rows=SearchRows()
        rows.add('CO','pichincha',True)
        rows.add('BR','bradesco',False)
        queries=rows.queries(1)
        self.assertEqual(len(queries),1)
        params=parse_qs(urlsplit(prepare(queries[0])[1]).query)
        self.assertEqual(params['country'],['CO'])
        self.assertEqual(params['q'],['pichincha'])

    def test_update_and_remove(self):
        """Verify that update and remove."""
        rows=SearchRows(); row_id=rows.add('CO','pichincha')
        rows.update(row_id,'br','bradesco',True)
        self.assertEqual(rows.queries(3)[0]['country'],'br')
        rows.remove(row_id)
        self.assertEqual(rows.queries(1),[])

    def test_invalid_row_does_not_change_existing_rows(self):
        """Verify that invalid row does not change existing rows."""
        rows=SearchRows(); row_id=rows.add('CO','pichincha')
        for country,criterion in [('ZZ','test'),('CO',' ' )]:
            with self.assertRaises(ValueError): rows.update(row_id,country,criterion,True)
        self.assertEqual(rows.get(row_id)['criterion'],'pichincha')

    def test_import_keeps_disabled_criteria_visible(self):
        """Verify that import keeps disabled criteria visible."""
        profile={'country':'co','enabled':True,'criteria':[{'query':'one','enabled':True},{'query':'two','enabled':False}]}
        rows=SearchRows(); rows.from_profiles([profile])
        self.assertEqual(len(rows.rows),2)
        self.assertFalse(rows.rows[1]['enabled'])


if __name__=='__main__': unittest.main()
