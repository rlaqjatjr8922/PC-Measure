import asyncio
import base64
from io import BytesIO
import unittest
from unittest.mock import patch
from PIL import Image
from fastapi.testclient import TestClient
import api
import server
from image_result import build

class Images(unittest.TestCase):
    def payload(self):
        out=BytesIO()
        Image.new('RGB',(3840,2160),(80,100,200)).save(out,format='PNG')
        return {'encoding':'base64','content_type':'image/png','data':base64.b64encode(out.getvalue()).decode(),'bytes':out.tell()}
    def test_mcp_image_block_without_base64_text(self):
        with patch('measure_tools.request',return_value=self.payload()):
            result=asyncio.run(api.mcp.call_tool('screen_screenshot',{'mode':'capture'}))
        self.assertEqual([x.type for x in result.content],['text','image'])
        self.assertNotIn('data',result.structured_content)
        self.assertEqual(result.structured_content['width'],1920)
        self.assertEqual(result.structured_content['original_width'],3840)
        self.assertEqual(result.content[1].mime_type,'image/jpeg')
    def test_browser_receives_image(self):
        with TestClient(server.app) as client,patch('measure_tools.request',return_value=self.payload()):
            r=client.post('/control/call',headers={'X-PC-Control':'1'},json={'name':'screen_screenshot','arguments':{'mode':'capture'}})
        self.assertTrue(r.json()['ok'])
        self.assertEqual(len(r.json()['images']),1)
    def test_bad_image_rejected(self):
        with self.assertRaises(ValueError):build({'encoding':'base64','content_type':'image/png','data':'not base64'})
    def test_non_image_unchanged(self):
        self.assertEqual(build({'hello':'world'}).structured_content,{'hello':'world'})
