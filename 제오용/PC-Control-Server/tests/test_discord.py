import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
import httpx
from plugins.discord import parser,reader
from remote import resolver,client
class Discord(unittest.TestCase):
 def setUp(self):
  resolver._state=None; resolver._checked=0
  settings=patch.object(resolver,'setting',side_effect=lambda name:'0001' if name=='REMOTE_PC_CODE' else '')
  settings.start(); self.addCleanup(settings.stop)
 def test_parser(self):
  self.assertEqual(parser.parse('0001 https://test.trycloudflare.com/'),'https://test.trycloudflare.com')
  for text in ['0002 https://test.trycloudflare.com','0001 http://test.trycloudflare.com','0001 https://test.trycloudflare.com.evil.com','0001 https://test.trycloudflare.com/path']:
   self.assertIsNone(parser.parse(text))
 def test_latest(self):
  with patch.object(reader,'messages',return_value=[{'id':'1','content':'0001 https://old.trycloudflare.com'},{'id':'3','content':'0001 https://new.trycloudflare.com'},{'id':'4','content':'0001 http://bad.com'}]):
   self.assertEqual(reader.latest('0001'),'https://new.trycloudflare.com')
 def test_cache_change_fallback(self):
  with tempfile.TemporaryDirectory(dir='tests') as folder,patch('plugins.discord.cache.path',return_value=Path(folder)/'cache.json'),patch.object(reader,'latest',side_effect=['https://old.trycloudflare.com','https://new.trycloudflare.com',RuntimeError('offline')]) as read:
   first=resolver.resolve(); resolver.confirmed(first)
   self.assertEqual(resolver.resolve(),first); self.assertEqual(read.call_count,1)
   second=resolver.resolve(True); resolver.confirmed(second)
   self.assertNotEqual(first['base_url'],second['base_url'])
   self.assertEqual(resolver.resolve(True),second)
   resolver._state=None
   self.assertEqual(resolver.cache.load('0001','')['base_url'],second['base_url'])
 def test_retry_new_address(self):
  real=httpx.Client; seen=[]
  def handler(req):
   seen.append(str(req.url))
   if len(seen)==1: raise httpx.ConnectError('offline')
   return httpx.Response(200,json={'ok':True})
  with patch.object(resolver,'resolve',side_effect=[{'base_url':'https://old.trycloudflare.com'},{'base_url':'https://new.trycloudflare.com'}]),patch.object(resolver,'confirmed'),patch.object(client.httpx,'Client',side_effect=lambda **kw:real(transport=httpx.MockTransport(handler),**kw)):
   self.assertTrue(client.request('/system/status')['response']['ok'])
  self.assertEqual(len(seen),2); self.assertIn('new.trycloudflare.com',seen[1])
 def test_status_missing_config(self):
  from remote.status import status
  with patch.object(resolver,'resolve',side_effect=RuntimeError('설정 필요')):
   self.assertFalse(status()['connected'])
