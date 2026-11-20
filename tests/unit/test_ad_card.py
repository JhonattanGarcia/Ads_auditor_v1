import tkinter as tk
import unittest
from unittest.mock import Mock
from brand_threat_monitor.ui.ad_card import card_data,AdCard


class AdCardTests(unittest.TestCase):
    def payload(self):
        return {'ad_id':'123','advertiser_id':'456','page':{'name':'Example Brand'},'is_active':True,
                'delivery_start_time':'2026-11-19T12:00:00+00:00',
                'creatives':[{'title':'A readable headline','body':'Full advertising text','link_url':'https://example.com/offer',
                              'image_url':'https://example.com/image.png','cta_text':'Learn more'},
                             {'title':'Second creative','body':'Another copy'}],
                'impressions':{'lower_bound':0,'upper_bound':100}}

    def test_card_extracts_human_fields_without_losing_zero_metrics(self):
        data=card_data(self.payload())
        self.assertEqual(data['name'],'Example Brand')
        self.assertEqual(data['domain'],'example.com')
        self.assertEqual(data['body'],'Full advertising text')
        self.assertEqual(data['status'],'Active')
        self.assertIn('0 - 100',data['metrics'])
        self.assertEqual(data['media_type'],'Image')

    def test_missing_fields_have_explicit_placeholders(self):
        data=card_data({})
        self.assertEqual(data['status'],'Status unavailable')
        self.assertEqual(data['start'],'Not available')
        self.assertEqual(data['domain'],'')

    def test_card_changes_creative_without_opening_external_links(self):
        root=tk.Tk(); root.withdraw(); callback=Mock()
        card=AdCard(root,on_open=callback)
        try:
            card.show(self.payload(),priority=1)
            self.assertEqual(card.name.cget('text'),'Example Brand')
            self.assertIn('Full advertising text',card.body.get('1.0','end'))
            card.change(1)
            self.assertEqual(card.title.cget('text'),'Second creative')
            callback.assert_not_called()
            card.show_message('No results')
            self.assertIn('No results',card.body.get('1.0','end'))
            self.assertEqual(str(card.copy_button.cget('state')),'disabled')
        finally: card.destroy(); root.destroy()

    def test_fixed_images_and_scrollable_half_width_text(self):
        root=tk.Tk(); root.geometry('1000x400')
        card=AdCard(root); card.pack(fill='both',expand=True)
        try:
            payload=self.payload(); payload['creatives']=[]
            payload['body']='Long ad text. '*1000
            card.show(payload)
            root.update()
            widths=[panel.winfo_width() for panel in (card.advertiser_panel,card.media_panel,card.text_panel)]
            self.assertLess(abs(widths[0]-widths[1]),3)
            self.assertLess(abs(widths[2]-2*widths[0]),15)
            before=(card.advertiser_panel.winfo_y(),card.media_panel.winfo_y())
            card.canvas.yview_moveto(1); root.update()
            self.assertEqual(before,(card.advertiser_panel.winfo_y(),card.media_panel.winfo_y()))
            self.assertGreater(card.canvas.yview()[0],0)
        finally: card.destroy(); root.destroy()

    def test_advertiser_picture_is_extracted(self):
        data=card_data({'page':{'profile_picture_url':'https://example.com/avatar.jpg'}})
        self.assertEqual(data['advertiser_images'],['https://example.com/avatar.jpg'])

    def test_image_clicks_open_profile_and_ad(self):
        from unittest.mock import patch
        root=tk.Tk(); root.withdraw(); card=AdCard(root)
        try:
            payload=self.payload(); payload['page']['page_url']='https://www.facebook.com/example'
            card.show(payload)
            with patch('brand_threat_monitor.ui.ad_card.webbrowser.open') as opened:
                card.open_publisher(); card.open_ad()
                self.assertEqual(opened.call_args_list[0].args[0],'https://www.facebook.com/example')
                self.assertEqual(opened.call_args_list[1].args[0],'https://www.facebook.com/ads/library/?id=123')
            card.show_message('Empty')
            with patch('brand_threat_monitor.ui.ad_card.webbrowser.open') as opened:
                card.open_publisher(); card.open_ad(); opened.assert_not_called()
        finally: card.destroy(); root.destroy()

    def test_external_links_include_all_creatives_and_unwrap_meta_redirects(self):
        from brand_threat_monitor.ui.ad_card import external_links
        payload={'creatives':[{'link_url':'https://l.facebook.com/l.php?u=https%3A%2F%2Fexample.com%2Foffer',
            'body':'Visit https://example.com/offer or www.other.com.',
            'image_url':'https://cdn.example.com/image.jpg'},
            {'link_url':'https://www.facebook.com/example','body':'https://third.com/path'}]}
        self.assertEqual(external_links(payload),['https://example.com/offer','https://www.other.com','https://third.com/path'])

    def test_profile_fallback_and_invalid_urls(self):
        data=card_data({'page':{'id':'456','page_url':'javascript:alert(1)'},'link_url':'javascript:alert(1)'})
        self.assertEqual(data['publisher_url'],'https://www.facebook.com/456')
        self.assertEqual(data['external_links'],[])

    def test_loaded_images_survive_switching_and_clearing(self):
        from PIL import Image
        root=tk.Tk(); root.withdraw(); card=AdCard(root)
        try:
            payload=self.payload(); payload['creatives']=[{},{}]
            card.show(payload)
            for action in (lambda:card.show(payload),lambda:card.change(1),lambda:card.show_message('Cleared')):
                card.display_image(Image.new('RGB',(30,30)),'media')
                card.display_image(Image.new('RGB',(30,30)),'advertiser')
                action()
                root.update_idletasks()
            self.assertEqual(str(card.media.cget('image')),'')
            self.assertEqual(str(card.advertiser_media.cget('image')),'')
        finally: card.destroy(); root.destroy()


if __name__=='__main__': unittest.main()
