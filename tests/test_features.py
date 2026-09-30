import ast
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock
from io import BytesIO

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import config, api_config, server
from fastapi.testclient import TestClient
from PIL import Image


def load(group,feature):
    spec=importlib.util.spec_from_file_location('test_'+group+'_'+feature,ROOT/group/(feature+'.py'))
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

class Features(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base=Path(self.temp.name)
        for name,value in {'DATA_DIR':base/'data','PRIVATE':base/'private','DB':base/'private'/'test.sqlite3'}.items():
            p=patch.object(config,name,value); p.start(); self.addCleanup(p.stop)
        config.KILL_SWITCH=False; config.stop_event.clear(); config.held_keys.clear(); config.held_buttons.clear()
        self.client=TestClient(server.app)
        self.addCleanup(self.client.close)
    def request(self,path,args=None,status=200):
        r=self.client.post(path,json=args or {})
        self.assertEqual(r.status_code,status,r.text)
        return r.json().get('result')
    def test_structure(self):
        self.assertEqual([r.path for r in server.app.routes],['/{group}/{feature}'])
        for group in ('core','macro','mission','history'):
            self.assertFalse((ROOT/group).exists())
            self.request('/'+group+'/list',status=404)
        self.assertEqual(self.client.post('/mcp',json={}).status_code,404)
        count=0
        for group,schema in vars(api_config).items():
            if group.startswith('_') or not isinstance(schema,dict): continue
            for feature in schema:
                self.assertTrue(callable(load(group,feature).run)); count+=1
        self.assertEqual(count,60)
        for p in ROOT.glob('*/*.py'):
            if p.parent.name=='tests': continue
            for node in ast.walk(ast.parse(p.read_text(encoding='utf-8-sig'))):
                if isinstance(node,ast.ImportFrom): self.assertFalse((node.module or '').startswith('core'))
    def test_file_lifecycle(self):
        self.request('/files/create',{'path':'temp:/a.txt','content':{'text':'한글'}})
        self.assertEqual(self.request('/files/read',{'path':'temp:/a.txt'})['content'],'한글')
        self.request('/files/save',{'path':'temp:/a.txt','content':{'text':'x'}},409)
        self.request('/files/edit',{'path':'temp:/a.txt','content':{'text':'수정'}})
        self.assertEqual(self.request('/files/info',{'path':'temp:/a.txt'})['size'],6)
        self.request('/files/copy',{'path':'temp:/a.txt','destination':'temp:/b.txt'})
        self.request('/files/move',{'path':'temp:/b.txt','destination':'temp:/c.txt'})
        self.request('/files/rename',{'path':'temp:/c.txt','name':'d.txt'})
        self.assertEqual(self.request('/files/list',{'path':'temp:/'})['total'],2)
        with patch('os.startfile') as launch:
            self.request('/files/open',{'path':'temp:/d.txt'}); launch.assert_called_once()
        self.request('/files/delete',{'path':'temp:/d.txt'})
        self.request('/files/read',{'path':'temp:/d.txt'},404)
        self.assertEqual(self.request('/temp/current')['alias'],'temp:/')
    def test_validation_and_http(self):
        for path,args,status in [('/files/read',{},400),('/files/read',{'path':'temp:/../escape'},403),('/files/read',{'path':str(ROOT/'config.py')},403),('/system/info',{'bad':1},400),('/input/mouse',{'mode':'bad'},400)]:
            self.request(path,args,status)
        for body in ('[1]','{'):
            self.assertEqual(self.client.post('/system/info',content=body).status_code,400)
        self.assertEqual(self.client.get('/system/info').status_code,200)
        self.request('/files/create',{'path':'temp:/a','content':{'text':'x'}})
        self.assertEqual(self.client.get('/files/read',params={'path':'temp:/a','options':json.dumps({'limit':1})}).status_code,200)
    def test_system(self):
        self.assertEqual(self.request('/system/status')['server'],'running')
        self.assertIn('os',self.request('/system/info'))
        self.assertIn('cpu_percent',self.request('/system/telemetry'))
        self.assertIsInstance(self.request('/system/processes'),list)
        executable=Path(self.temp.name)/'fake.exe'; executable.write_bytes(b'test')
        with patch('subprocess.Popen') as start:
            start.return_value.pid=123
            self.assertEqual(self.request('/system/start_app',{'executable':str(executable)})['pid'],123)
        cb=MagicMock(); cb.GetClipboardData.return_value='text'
        with patch.dict(sys.modules,{'win32clipboard':cb}):
            self.assertEqual(self.request('/system/clipboard',{'mode':'read'})['text'],'text')
            self.request('/system/clipboard',{'mode':'write','text':'new'})
    def test_mouse_and_keyboard(self):
        for feature in api_config.mouse:
            m=load('mouse',feature); gui=MagicMock(); gui.position.return_value=(10,20)
            args={'x':3,'y':4,'options':{'interval':0},'amount':1,'start_x':1,'start_y':2,'end_x':3,'end_y':4}
            with patch.object(m,'_gui',return_value=gui):
                if hasattr(m,'_move'):
                    with patch.object(m,'_move',return_value={'x':3,'y':4}): result=m.run(**args)
                else: result=m.run(**args)
            self.assertIsInstance(result,dict)
            self.assertFalse(config.held_buttons)
        for feature in api_config.keyboard:
            m=load('keyboard',feature); gui=MagicMock(); gui.KEYBOARD_KEYS=['a','b']
            with patch.object(m,'_gui',return_value=gui):
                if feature=='type':
                    with patch.object(m,'_unicode_char') as unicode: m.run(text='한',interval=0); unicode.assert_called_once()
                else: m.run(key='a',keys=['a','b'])
        m=load('input','mouse'); gui=MagicMock(); gui.position.return_value=(10,20)
        with patch.object(m,'_gui',return_value=gui),patch.object(m,'_move',return_value={'x':3,'y':4}):
            for mode,args in api_config.input['mouse']['mode'].items():
                values={k:(2 if v is None else v) for k,v in args.items()}; values['duration']=0
                if mode in ('position','scroll'): values.pop('duration',None)
                m.run(mode,**values)
        m=load('input','keyboard'); gui.KEYBOARD_KEYS=['a']
        with patch.object(m,'_gui',return_value=gui),patch.object(m,'_unicode_char'):
            for mode,args in api_config.input['keyboard']['mode'].items():
                values={k:('a' if k in ('key','text') else ['a'] if k=='keys' else v) for k,v in args.items()}
                m.run(mode,**values)
    def test_window(self):
        wg=MagicMock(); wp=MagicMock(); wg.IsWindow.return_value=True
        wg.GetWindowRect.return_value=(0,0,100,100); wg.GetWindowText.return_value='Test'
        wg.GetWindowPlacement.return_value=(0,0); wp.GetWindowThreadProcessId.return_value=(0,123)
        wg.GetForegroundWindow.return_value=1
        wg.EnumWindows.side_effect=lambda cb,arg:cb(1,arg)
        with patch.dict(sys.modules,{'win32gui':wg,'win32process':wp}):
            for feature in api_config.window:
                m=load('window',feature)
                if feature=='window':
                    for mode,args in api_config.window['window']['mode'].items():
                        m.run(mode,**{k:('Test' if k=='title' else 10) for k in args})
                elif feature=='position':
                    m.run(hwnd=1,mode='get'); m.run(hwnd=1,mode='set',x=0,y=0,width=10,height=10)
                else: m.run(hwnd=1,title='Test')
    def test_screen_and_verify(self):
        raw=BytesIO(); Image.new('RGB',(4,3),'white').save(raw,format='PNG'); raw=raw.getvalue()
        area={'left':0,'top':0,'width':4,'height':3}
        m=load('screen','screenshot')
        with patch.object(m,'_capture',return_value=(raw,area)):
            a=m.run(mode='save',target={}); self.assertEqual(m.run(mode='capture',target={}),raw)
        self.assertEqual(m.run(mode='read',screenshot_id=a['id']),raw)
        m=load('screen','marker')
        mark=m.run(mode='add',screenshot_id=a['id'],data={'x':1,'y':1})
        self.assertEqual(m.run(mode='get',marker_id=mark['id'])['x'],1)
        m.run(mode='update',marker_id=mark['id'],data={'x':2})
        self.assertEqual(len(m.run(mode='list',screenshot_id=a['id'])),1)
        m.run(mode='delete',marker_id=mark['id'])
        for feature in api_config.verify:
            m=load('verify',feature)
            with patch.object(m,'_capture',return_value=(raw,area)):
                if feature=='hash': self.assertEqual(m.run(target={})['hash'],a['hash'])
                elif feature=='wait_stable': self.assertTrue(m.run(target={},options={'interval':.02,'stable_for':.02,'max_wait':1})['stable'])
                else:
                    result=m.run(mode='current',before_id=a['id'],target={},tolerance=0)
                    self.assertFalse(result['changed'])
                    if feature=='assert_unchanged': self.assertTrue(result['passed'])
                    if feature=='assert_changed': self.assertFalse(result['passed'])
    def test_telemetry_counts(self):
        before=self.request('/system/telemetry')
        self.request('/system/info')
        self.request('/files/read',{},400)
        after=self.request('/system/telemetry')
        self.assertEqual(after['requests']-before['requests'],3)
        self.assertEqual(after['errors']-before['errors'],1)
        self.assertGreaterEqual(after['duration_ms'],before['duration_ms'])

    def test_stop_cancels_and_persists(self):
        import sqlite3
        from contextlib import closing
        question=self.request('/interaction/ask_user',{'question':'pending'})
        m=load('safety','kill_switch')
        with patch.object(m,'_release_all',side_effect=RuntimeError('mock release failure')):
            result=m.run(reason='test reason')
        self.assertEqual(result['cancelled_questions'],1)
        self.assertEqual(result['input_release_error'],'RuntimeError')
        self.assertEqual(self.request('/interaction/questions')[0]['state'],'cancelled')
        self.request('/interaction/answer',{'question_id':question['id'],'answer':'no'},409)
        self.request('/interaction/ask_user',{'question':'new'},409)
        with closing(sqlite3.connect(config.DB)) as db:
            entry=json.loads(db.execute("SELECT value FROM objects WHERE kind='stop'").fetchone()[0])
        self.assertEqual(entry['reason'],'test reason')
        config.KILL_SWITCH=False; config.stop_event.clear()

    def test_release_continues_after_failure(self):
        config.held_keys.update(['a','b']); config.held_buttons.add('left')
        m=load('safety','kill_switch'); gui=MagicMock(); gui.position.return_value=(0,0)
        gui._pyautogui_win._keyUp.side_effect=lambda key: (_ for _ in ()).throw(RuntimeError()) if key=='a' else None
        with patch.object(m,'_gui',return_value=gui):
            with self.assertRaises(RuntimeError): m._release_all()
        self.assertEqual(gui._pyautogui_win._keyUp.call_count,2)
        gui._pyautogui_win._mouseUp.assert_called_once()
        self.assertEqual(config.held_keys,{'a'}); self.assertFalse(config.held_buttons)
        config.held_keys.clear()

    def test_capture_endpoints(self):
        sct=MagicMock()
        sct.monitors=[{'left':0,'top':0,'width':4,'height':3}]*2
        shot=MagicMock(); shot.rgb=bytes([255]*36); shot.size=(4,3)
        sct.grab.return_value=shot
        wg=MagicMock(); wg.FindWindow.return_value=1; wg.GetWindowRect.return_value=(0,0,4,3)
        wg.EnumWindows.side_effect=lambda cb,arg:cb(1,arg)
        wg.GetWindowText.return_value='Test'
        with patch('mss.mss') as capture,patch.dict(sys.modules,{'win32gui':wg}):
            capture.return_value.__enter__.return_value=sct
            self.request('/screen/capture_monitor',{'monitor':1})
            for mode in ('all','monitor','windows'):
                self.request('/screen/monitors',{'mode':mode,**({'monitor':1} if mode=='monitor' else {})})
            for args in ({'mode':'full','monitor':1},{'mode':'window','window':'Test'},{'mode':'region','monitor':1,'x':0,'y':0,'width':4,'height':3}):
                response=self.client.post('/screen/capture',json=args)
                self.assertEqual(response.status_code,200,response.text)
                self.assertEqual(response.headers['content-type'],'image/png')
            self.request('/screen/capture',{'mode':'region','monitor':1,'x':0,'y':0,'width':0,'height':3},400)

    def test_interaction_watch_and_stop(self):
        q=self.request('/interaction/ask_user',{'question':'test','options':['yes']})
        self.assertEqual(self.request('/interaction/status',{'question_id':q['id']})['state'],'pending')
        self.assertEqual(len(self.request('/interaction/questions')),1)
        self.assertEqual(self.request('/interaction/answer',{'question_id':q['id'],'answer':'yes'})['state'],'answered')
        self.request('/interaction/answer',{'question_id':q['id'],'answer':'yes'},409)
        self.request('/watch/start',status=409)
        self.assertEqual(self.request('/watch/list'),[])
        self.request('/watch/status',{'watch_id':'missing'},404)
        self.request('/watch/stop',{'watch_id':'missing'},404)
        m=load('safety','kill_switch')
        with patch.object(m,'_release_all'):
            self.assertTrue(m.run(reason='test')['stopped'])
        self.request('/files/create',{'path':'temp:/stop','content':{'text':'x'}},409)
        config.KILL_SWITCH=False; config.stop_event.clear()

if __name__=='__main__': unittest.main(verbosity=2)
