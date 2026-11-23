from io import BytesIO
import unittest
from unittest.mock import MagicMock,patch
from PIL import Image
from brand_threat_monitor.ui.remote_image import load_remote_image,MAX_BYTES
from brand_threat_monitor.ui.ad_card import card_data


class RemoteImageTests(unittest.TestCase):
    def response(self,content):
        """Build the controlled response fixture used by this test scenario."""
        response=MagicMock()
        response.__enter__.return_value=response
        response.geturl.return_value='https://example.com/image'
        response.read.return_value=content
        return response

    def test_decodes_download_and_limits_thumbnail(self):
        """Verify that decodes download and limits thumbnail."""
        stream=BytesIO()
        Image.new('RGB',(800,600)).save(stream,format='PNG')
        with patch('brand_threat_monitor.ui.remote_image.urlopen',return_value=self.response(stream.getvalue())) as opened:
            image=load_remote_image('https://example.com/image')
        self.assertEqual(image.size,(400,300))
        self.assertEqual(opened.call_args.kwargs['timeout'],8)

    def test_invalid_and_oversized_downloads(self):
        """Verify that invalid and oversized downloads."""
        for content in (b'not an image',b'x'*(MAX_BYTES+1)):
            with patch('brand_threat_monitor.ui.remote_image.urlopen',return_value=self.response(content)):
                with self.assertRaises((ValueError,OSError)):
                    load_remote_image('https://example.com/image')

    def test_non_web_urls_are_rejected(self):
        """Verify that non web urls are rejected."""
        with self.assertRaises(ValueError): load_remote_image('file:///tmp/image.png')

    def test_video_uses_thumbnail_not_video_as_image(self):
        """Verify that video uses thumbnail not video as image."""
        data=card_data({'creatives':[{'video_url':'https://example.com/video.mp4','thumbnail_url':'https://example.com/preview.jpg'}]})
        self.assertEqual(data['images'],['https://example.com/preview.jpg'])
        self.assertEqual(data['media_type'],'Video')
