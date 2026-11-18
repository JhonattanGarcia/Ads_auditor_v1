import json
import tkinter as tk
import unittest

from brand_threat_monitor.ui.information import format_information,InformationWindow


class InformationTests(unittest.TestCase):
    def test_nested_fields_are_complete_without_json_syntax(self):
        data={'advertiser_id':'00123','creatives':[{'body':'Full ad text','unknown_source_field':{'metric':0,'active':False}}],
              'targeting':{'countries':['CO','BR']},'missing':None}
        text=format_information(data)
        for value in ['00123','Full ad text','Unknown source field','Metric: 0','Active: No','CO','BR','Missing: Not available']:
            self.assertIn(value,text)
        self.assertNotIn('{',text)
        self.assertNotIn('"advertiser_id"',text)

    def test_serialized_audit_payloads_are_decoded_as_fields(self):
        text=format_information({'before_json':json.dumps({'decision':'spam'}),
                                 'after_json':json.dumps({'decision':None})})
        self.assertIn('Before change',text)
        self.assertIn('Decision: spam',text)
        self.assertIn('Decision: Not available',text)
        self.assertNotIn('{',text)

    def test_false_zero_empty_and_missing_remain_distinct(self):
        text=format_information({'flag':False,'count':0,'text':'','values':[],'missing':None})
        for value in ['Flag: No','Count: 0','(empty text)','None recorded','Not available']:
            self.assertIn(value,text)

    def test_unknown_fields_and_long_values_can_be_read_in_full(self):
        root=tk.Tk(); root.withdraw()
        value='Long source text\n'+'x'*2000
        window=InformationWindow(root,{'source_details':{'new_field':value}}); window.withdraw()
        try:
            field=next(item for item,(key,content) in window.values.items() if key=='new_field')
            window.tree.selection_set(field); window.select()
            self.assertEqual(window.value.get('1.0','end-1c'),value)
            self.assertEqual(window.tree.item(field,'text'),'New field')
        finally: window.destroy(); root.destroy()


if __name__=='__main__': unittest.main()
