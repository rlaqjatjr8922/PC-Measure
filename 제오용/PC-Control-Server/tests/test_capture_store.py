import asyncio
import base64
from io import BytesIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import httpx
from PIL import Image
import api
import capture_store
from remote import client as remote_client
from image_result import build
from fastapi.testclient import TestClient
import server

class ControllerCapture(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='capture-store-test-')
        self.addCleanup(self.temp.cleanup)
        p=patch.object(capture_store,'_folder',self.temp);p.start();self.addCleanup(p.stop)
        out=BytesIO();Image.new('RGB',(50,30),(45,90,120)).save(out,format='PNG');self.raw=out.getvalue()
        self.original_client=httpx.Client
        self.seen=[]
    def handler(self,request):
        self.seen.append(request)
        return httpx.Response(200,content=self.raw,headers={'content-type':'image/png'})
    def bridge(self):
        return patch.object(remote_client.httpx,'Client',side_effect=lambda **kw:self.original_client(transport=httpx.MockTransport(self.handler),**kw))
    def test_receive_stores_locally_and_mcp_reads_that_file(self):
        with patch('remote.client.resolver.resolve',return_value={'base_url':'https://guest.example'}),patch('remote.client.resolver.confirmed'),self.bridge():
            result=asyncio.run(api.mcp.call_tool('screen_screenshot',{'mode':'capture'}))
        self.assertEqual(len(self.seen),1)
        self.assertEqual(self.seen[0].url.path,'/screen/screenshot')
        self.assertEqual(__import__('json').loads(self.seen[0].content)['mode'],'capture')
        meta=result.structured_content
        self.assertEqual(meta['storage'],'controller_temp')
        self.assertEqual(Path(meta['local_path']).read_bytes(),self.raw)
        with Image.open(BytesIO(base64.b64decode(result.content[1].data))) as picture:
            self.assertEqual(picture.size,(50,30))
        self.assertNotIn('data',meta)
    def test_direct_http_returns_original_from_local_file(self):
        c=TestClient(server.app);self.addCleanup(c.close)
        with patch('remote.client.resolver.resolve',return_value={'base_url':'https://guest.example'}),patch('remote.client.resolver.confirmed'),self.bridge():
            result=c.post('/screen/capture_monitor',json={'monitor':1})
        self.assertEqual(result.status_code,200)
        self.assertEqual(result.content,self.raw)
        files=list(Path(self.temp.name).iterdir());self.assertEqual(len(files),1)
        self.assertEqual(files[0].read_bytes(),result.content)
    def test_reader_uses_disk_and_rejects_outside_path(self):
        record=capture_store.save(self.raw,'image/png')
        replacement=BytesIO();Image.new('RGB',(12,10),'red').save(replacement,format='PNG')
        Path(record['local_path']).write_bytes(replacement.getvalue())
        self.assertEqual(build(record).structured_content['original_width'],12)
        record['local_path']=str(Path(self.temp.name).parent/'outside.png')
        with self.assertRaises(ValueError):capture_store.read(record)
    def test_unique_files_and_bounded_cleanup(self):
        a=capture_store.save(self.raw,'image/png');b=capture_store.save(self.raw,'image/png')
        self.assertNotEqual(a['local_path'],b['local_path'])
        with patch.object(capture_store,'MAX_FILES',2):
            c=capture_store.save(self.raw,'image/png')
        self.assertFalse(Path(a['local_path']).exists())
        self.assertTrue(Path(c['local_path']).exists())
        with patch.object(capture_store,'MAX_IMAGE',2):
            with self.assertRaises(ValueError):capture_store.save(self.raw,'image/png')
