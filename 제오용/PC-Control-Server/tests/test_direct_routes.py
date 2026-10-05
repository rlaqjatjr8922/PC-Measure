import json
import sys
from pathlib import Path
import unittest
from unittest.mock import patch
import httpx
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
import remote_client, server

class DirectRoutes(unittest.TestCase):
    def setUp(self):
        self.client=TestClient(server.app); self.addCleanup(self.client.close)
        self.http_client=httpx.Client
        resolver=patch('remote.client.resolver.resolve',return_value={'base_url':'https://test.trycloudflare.com'}); resolver.start(); self.addCleanup(resolver.stop)
        cache=patch('remote.client.resolver.confirmed'); cache.start(); self.addCleanup(cache.stop)
    def mock(self,handler):
        return patch('remote.client.httpx.Client',side_effect=lambda **kw:self.http_client(transport=httpx.MockTransport(handler),**kw))
    def test_all_60_paths_get_and_post(self):
        self.assertEqual(len(remote_client.ALLOWED_PATHS),66)
        for path in sorted(remote_client.ALLOWED_PATHS):
            for method in ('GET','POST'):
                with self.subTest(path=path,method=method):
                    seen=[]
                    def handler(req):
                        seen.append(req)
                        self.assertEqual(req.url.path,path); self.assertEqual(req.method,method)
                        return httpx.Response(200,json={'success':True,'result':{'test':True}})
                    with self.mock(handler): r=self.client.request(method,path)
                    self.assertEqual(r.status_code,200); self.assertEqual(len(seen),1)
                    self.assertEqual(r.json(),{'success':True,'result':{'test':True}})
    def test_modes_options_and_query(self):
        def handler(req):
            self.assertEqual(json.loads(req.content),{'mode':'set','hwnd':1,'x':20,'y':30,'width':400,'height':300})
            return httpx.Response(200,json={'success':True,'result':{}})
        with self.mock(handler):
            r=self.client.post('/window/position?mode=get',json={'mode':'set','hwnd':1,'x':20,'y':30,'width':400,'height':300})
        self.assertEqual(r.status_code,200)
        def handler_get(req):
            self.assertEqual(json.loads(req.url.params['options']),{'limit':10})
            return httpx.Response(200,json={'success':True,'result':{}})
        with self.mock(handler_get):
            r=self.client.get('/files/read',params={'path':'temp:/a','options':'{"limit":10}'})
        self.assertEqual(r.status_code,200)
    def test_png_returned_as_image(self):
        image=b'\x89PNG\r\n\x1a\nfixture'
        with self.mock(lambda r:httpx.Response(200,content=image,headers={'content-type':'image/png'})):
            r=self.client.post('/screen/screenshot',json={'mode':'capture'})
        self.assertEqual(r.content,image); self.assertEqual(r.headers['content-type'],'image/png')
    def test_remote_failure(self):
        with self.mock(lambda r:httpx.Response(409,json={'success':False,'error':'WATCH_CONDITION_UNDEFINED'})):
            r=self.client.post('/watch/start')
        self.assertEqual(r.status_code,409)
        self.assertEqual(r.json(),{'success':False,'error':'WATCH_CONDITION_UNDEFINED'})
    def test_bad_json_not_forwarded(self):
        with patch('remote_routes.remote_request') as call:
            for raw in ('[]','{','null'):
                self.assertEqual(self.client.post('/mouse/click',content=raw).status_code,400)
            call.assert_not_called()
    def test_existing_routes_and_unknown_paths(self):
        self.assertEqual(self.client.get('/').status_code,200)
        self.assertEqual(self.client.post('/mouse/not_registered').status_code,404)
        paths=set(server.app.openapi()['paths'])
        self.assertTrue({'/history/{feature}','/log/{feature}','/mcp/mission/{feature}','/remote/{feature}'}.issubset(paths))

if __name__=='__main__': unittest.main(verbosity=2)

