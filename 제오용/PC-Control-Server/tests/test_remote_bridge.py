import asyncio
import unittest
from unittest.mock import patch
import httpx
import api
from remote import client
class Tools(unittest.TestCase):
 def test_registry(self):
  names={t.name for t in asyncio.run(api.mcp.list_tools())}
  self.assertEqual(len(names),81); self.assertNotIn('remote_call',names)
  self.assertTrue({'system_powershell_normal','system_powershell_admin'} <= names)
  self.assertNotIn('system_powershell',names)
  with self.assertRaises(Exception): asyncio.run(api.mcp.call_tool('remote_call',{}))
 def test_every_tool_mode(self):
  from measure_tools import REMOTE_GROUPS
  from jsonschema import validate
  registry=api.configured_tools(api.read_api_config()); count=0
  for name,(group,feature,params,_) in registry.items():
   if group not in REMOTE_GROUPS: continue
   variants=params.get('mode',{None:params})
   for mode,fields in variants.items():
    args={} if mode is None else {'mode':mode}
    for k,v in fields.items():
     if v is not ...: continue
     args[k]=({'text':'test'} if k=='content' else {} if k=='data' else ['a'] if k=='keys' else 1 if k in ('x','y','start_x','start_y','end_x','end_y','hwnd','width','height','window','monitor','amount') else 'test')
    validate(args,api.tool_schema(params,group,feature))
    with patch('measure_tools.request',return_value={'response':{'ok':True}}) as req:
     result=asyncio.run(api.mcp.call_tool(name,args))
     expected='/system/powershell' if feature in ('powershell_normal','powershell_admin') else '/'+group+'/'+feature
     self.assertTrue(result.structured_content['ok']); self.assertEqual(req.call_args.args[0],expected)
    count+=1
  self.assertEqual(count,103)
 def test_powershell_privileges_are_fixed(self):
  for privilege in ('normal','admin'):
   name='system_powershell_'+privilege
   with patch('measure_tools.request',return_value={'response':{'ok':True}}) as req:
    asyncio.run(api.mcp.call_tool(name,{'command':'Write-Output test'}))
    self.assertEqual(req.call_args.args,('/system/powershell',{'command':'Write-Output test','privilege':privilege,'timeout':60}))
    req.reset_mock()
    with self.assertRaises(Exception):
     asyncio.run(api.mcp.call_tool(name,{'command':'test','privilege':'admin' if privilege=='normal' else 'normal'}))
    req.assert_not_called()
 def test_required(self):
  for name,args in [('mouse_click',{}),('keyboard_type',{'text':' '}),('screen_capture',{'mode':'window'}),('mouse_click',{'x':'1','y':2})]:
   with self.assertRaises(Exception): asyncio.run(api.mcp.call_tool(name,args))
