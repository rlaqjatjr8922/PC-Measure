import asyncio
import importlib.util
from io import BytesIO
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch, MagicMock
from PIL import Image
from fastapi.testclient import TestClient
import api_config
import config
import server
from core import runtime as rt
from core import macros


class Endpoints(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        root=Path(self.folder.name)
        self.patchers=[patch.object(rt,'PRIVATE',root/'private'),patch.object(rt,'DB',root/'private'/'state.sqlite3'),patch.object(rt,'DATA',root/'data')]
        for p in self.patchers:
            p.start(); self.addCleanup(p.stop)
        rt.active=None
        rt.context.set(None)
        rt.stop_event.clear()
        config.KILL_SWITCH=False
        macros.recording=None
        macros.replaying=False
        self.client=TestClient(server.app)
        self.addCleanup(self.client.close)
        self.user={'x-user-key':rt.user_key()}
        self.headers={}

    def call(self,path,body=None,user=False):
        return self.client.post(path,json=body or {},headers=self.user if user else self.headers)

    def select(self,name='작업'):
        res=self.call('/history/create',{'name':name},True)
        self.assertEqual(res.status_code,200,res.text)
        result=res.json()['result']
        self.headers={'x-mission-context':result['context_id']}
        return result['mission']

    def png(self,color):
        out=BytesIO();Image.new('RGB',(4,3),color).save(out,format='PNG');return out.getvalue()

    def test_registration_and_arguments(self):
        count=0
        for group,features in vars(api_config).items():
            if group.startswith('_') or not isinstance(features,dict):continue
            for feature,fields in features.items():
                file=rt.BASE/group/(feature+'.py')
                self.assertTrue(file.is_file(),str(file))
                spec=importlib.util.spec_from_file_location('test_feature',file)
                module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
                self.assertTrue(callable(module.run));count+=1
        self.assertGreaterEqual(count,75)
        self.assertEqual(self.call('/invalid/feature').status_code,404)
        self.assertEqual(self.call('/mouse/click',{'x':1}).status_code,400)
        self.assertEqual(self.call('/mouse/click',{'x':1,'y':2,'bad':3}).status_code,400)
        self.assertEqual(server.build_arguments({'x':3},{'x':8}),{'x':8})
        self.assertEqual(server.build_arguments({'x':3},{}),{'x':3})
        self.assertEqual(self.client.post('/system/status',content='{').status_code,400)

    def test_mission_history_isolation_and_restart(self):
        self.assertEqual(self.call('/history/create',{'name':'bad'}).status_code,403)
        self.assertEqual(self.call('/mission/status',{'mode':'get'}).status_code,409)
        a=self.select('첫 작업')
        self.assertEqual(self.call('/mission/plan',{'mode':'write','text':'계획 A'}).status_code,200)
        self.assertEqual(self.call('/mission/workflow',{'mode':'write','text':'수정','version':0}).status_code,409)
        self.assertEqual(self.call('/mission/work_log',{'mode':'add','entry':{'action':'test','success':True}}).status_code,200)
        first_headers=dict(self.headers)
        b=self.select('둘째 작업')
        self.assertEqual(self.call('/mission/work_log',{'mode':'list'}).json()['result'],[])
        stale=self.client.post('/mission/status',json={'mode':'get'},headers=first_headers)
        self.assertEqual(stale.status_code,409)
        res=self.call('/history/select',{'mission_id':a['id']},True).json()['result']
        self.headers={'x-mission-context':res['context_id']}
        self.assertEqual(res['mission']['plan'],'계획 A')
        self.assertEqual(len(res['work_log']),1)
        self.assertEqual(len(self.call('/history/load',{'mission_id':a['id']},True).json()['result']['work_log']),1)
        self.assertEqual(self.call('/mission/run').status_code,200)
        self.assertEqual(self.call('/history/create',{'name':'blocked'},True).status_code,409)
        self.assertEqual(len(self.call('/history/list',user=True).json()['result']),2)
        rt.active=None
        self.headers={}
        self.assertEqual(len(self.call('/history/list',user=True).json()['result']),2)
        self.assertEqual(self.call('/mission/status',{'mode':'get'}).status_code,409)

    def test_file_operations_and_protection(self):
        self.select()
        self.assertEqual(self.call('/temp/current').status_code,200)
        self.assertEqual(self.call('/files/create',{'path':'temp:/one.txt','content':{'text':'한글'}}).status_code,200)
        self.assertEqual(self.call('/files/create',{'path':'temp:/one.txt'}).status_code,409)
        self.assertEqual(self.call('/files/read',{'path':'temp:/one.txt'}).json()['result']['content'],'한글')
        self.assertEqual(self.call('/files/edit',{'path':'temp:/one.txt','content':{'text':'바꿈'}}).status_code,200)
        self.assertEqual(self.call('/files/copy',{'path':'temp:/one.txt','destination':'temp:/two.txt'}).status_code,200)
        self.assertEqual(self.call('/files/rename',{'path':'temp:/two.txt','name':'renamed.txt'}).status_code,200)
        self.assertEqual(self.call('/files/create',{'path':'temp:/folder','kind':'directory'}).status_code,200)
        self.assertEqual(self.call('/files/move',{'path':'temp:/renamed.txt','destination':'temp:/folder/moved.txt'}).status_code,200)
        self.assertEqual(self.call('/files/delete',{'path':'temp:/folder','options':{'recursive':True}}).status_code,200)
        self.assertEqual(len(self.call('/files/list',{'path':'temp:/'}).json()['result']['items']),1)
        self.assertEqual(self.call('/files/save',{'path':'temp:/one.txt','content':{'text':''},'options':{'overwrite':True}}).status_code,200)
        self.assertEqual(self.call('/files/read',{'path':str(rt.PRIVATE/'user.key')}).status_code,403)
        self.assertEqual(self.call('/files/read',{'path':'temp:/../../escape'}).status_code,403)
        self.assertEqual(self.call('/files/read',{'path':str(rt.BASE/'server.py')}).status_code,403)
        self.assertEqual(self.call('/files/delete',{'path':str(rt.PRIVATE.parent),'options':{'recursive':True}}).status_code,403)

    def test_screenshot_markers_and_verification(self):
        self.select()
        area={'left':0,'top':0,'width':4,'height':3}
        raw=self.png('black')
        with patch('core.imaging.capture',return_value=(raw,area)):
            response=self.call('/screen/screenshot',{'mode':'capture'})
            self.assertEqual(response.content,raw)
            self.assertIn('image/png',response.headers['content-type'])
            a=self.call('/screen/screenshot',{'mode':'save'}).json()['result']['id']
            b=self.call('/verify/hash').json()['result']['id']
            result=self.call('/verify/assert_unchanged',{'mode':'saved','before_id':a,'after_id':b}).json()['result']
            self.assertTrue(result['passed'])
            stable=self.call('/verify/wait_stable',{'options':{'interval':.02,'stable_for':.03,'max_wait':.2}}).json()['result']
            self.assertTrue(stable['stable'])
        with patch('core.imaging.capture',return_value=(self.png('white'),area)):
            changed=self.call('/verify/assert_changed',{'mode':'current','before_id':a}).json()['result']
            self.assertTrue(changed['passed']);self.assertEqual(changed['changed_ratio'],1)
        marker=self.call('/screen/marker',{'mode':'add','screenshot_id':a,'data':{'x':1,'y':2,'annotation':'메모'}}).json()['result']
        self.assertEqual(self.call('/screen/marker',{'mode':'update','marker_id':marker['id'],'data':{'annotation':'수정'}}).status_code,200)
        self.assertEqual(self.call('/screen/screenshot',{'mode':'read','screenshot_id':a}).content,raw)
        self.assertEqual(self.call('/screen/marker',{'mode':'delete','marker_id':marker['id']}).status_code,200)
        self.select('다른 작업')
        self.assertEqual(self.call('/screen/screenshot',{'mode':'read','screenshot_id':a}).status_code,403)

    def test_question_watch_and_stop(self):
        self.select()
        question=self.call('/interaction/ask_user',{'question':'어느 파일?'}).json()['result']
        self.assertEqual(question['state'],'pending')
        self.assertEqual(self.call('/interaction/answer',{'question_id':question['id'],'answer':'A'}).status_code,403)
        self.assertEqual(self.call('/interaction/answer',{'question_id':question['id'],'answer':'A'},True).status_code,200)
        self.assertEqual(self.call('/interaction/status',{'question_id':question['id']}).json()['result']['answer'],'A')
        self.assertEqual(self.call('/watch/start').status_code,409)
        self.assertEqual(self.call('/watch/list').json()['result'],[])
        with patch('core.desktop.release_all'):
            self.assertEqual(self.call('/safety/kill_switch').status_code,200)
        with patch('core.desktop.gui') as mock_gui:
            self.assertEqual(self.call('/mouse/click',{'x':1,'y':1}).status_code,409)
            mock_gui.return_value.click.assert_not_called()
        self.assertEqual(self.call('/mission/status',{'mode':'get'}).json()['result']['state'],'cancelled')
        self.assertEqual(self.call('/mission/run').status_code,409)
        self.assertEqual(self.call('/system/status').status_code,200)

    def test_macro_automation_and_audit(self):
        self.select()
        recorded=self.call('/macro/record',{'name':'테스트'}).json()['result']
        with patch('core.desktop.keyboard',return_value={'keys':['a']}):
            self.assertEqual(self.call('/keyboard/press',{'key':'a'}).status_code,200)
        self.assertEqual(self.call('/macro/stop').json()['result']['events'],1)
        with patch('core.desktop.keyboard',return_value={}) as command, patch('core.desktop.release_all'):
            res=self.call('/macro/replay',{'macro_id':recorded['id']})
            self.assertEqual(res.status_code,200,res.text)
            self.assertEqual(res.json()['result']['executed'],1)
            command.assert_called_once()
        self.client.post('/system/status',json={'password':'hidden-secret'},headers=self.user)
        audit=(rt.PRIVATE/'server.jsonl').read_text(encoding='utf-8')
        self.assertNotIn(rt.user_key(),audit)
        self.assertNotIn('hidden-secret',audit)
        rows=[json.loads(line) for line in audit.splitlines()]
        self.assertTrue(all({'timestamp','request_id','method','path','parameters','body','response','status','duration_ms','error'} <= row.keys() for row in rows))
        self.assertEqual(self.call('/server/logs').status_code,404)


    def test_desktop_arguments_without_live_input(self):
        self.select()
        with patch('core.desktop.gui') as gui, patch('core.desktop.move', return_value={'x':10,'y':20}) as move:
            gui.return_value.position.return_value=(10,20)
            self.assertEqual(self.call('/mouse/double_click',{'x':10,'y':20,'options':{'interval':0}}).status_code,200)
            self.assertEqual(gui.return_value.mouseDown.call_count,2)
            move.assert_called_with(10,20,0)
            self.assertEqual(self.call('/mouse/drag',{'start_x':1,'start_y':2,'end_x':3,'end_y':4,'options':{'duration':.5}}).status_code,200)
            move.assert_called_with(3,4,.5)
            self.assertEqual(rt.held_buttons,set())
            self.assertEqual(self.call('/mouse/scroll',{'amount':'nan'}).status_code,400)
        with patch('core.desktop.gui') as gui, patch('core.desktop.unicode_char') as unicode:
            gui.return_value.KEYBOARD_KEYS=['a','ctrl','shift']
            self.assertEqual(self.call('/keyboard/type',{'text':'한글A'}).status_code,200)
            self.assertEqual(unicode.call_count,3)
            self.assertEqual(self.call('/keyboard/hold',{'key':'ctrl'}).status_code,200)
            self.assertIn('ctrl',rt.held_keys)
            self.assertEqual(self.call('/keyboard/release',{'key':'ctrl'}).status_code,200)
            self.assertNotIn('ctrl',rt.held_keys)
            self.assertEqual(self.call('/keyboard/hotkey',{'keys':['ctrl','a']}).status_code,200)
            self.assertEqual(rt.held_keys,set())
            self.assertEqual(self.call('/keyboard/press',{'key':'not-a-key'}).status_code,400)
        with patch('win32gui.IsWindow',return_value=False):
            self.assertEqual(self.call('/window/state',{'hwnd':1234}).json()['result']['exists'],False)
            self.assertEqual(self.call('/window/focus',{'hwnd':1234}).status_code,404)

    def test_user_macro_recording_and_stop(self):
        self.select()
        with patch('pynput.keyboard.Listener') as keys, patch('pynput.mouse.Listener') as mouse:
            rec=self.call('/macro/record',{'name':'user sample','source':'user'})
            self.assertEqual(rec.status_code,200,rec.text)
            key=MagicMock();key.vk=65
            keys.call_args.kwargs['on_press'](key,False)
            keys.call_args.kwargs['on_release'](key,False)
            keys.call_args.kwargs['on_press'](key,True)  # Injected event is excluded.
            mouse.call_args.kwargs['on_move'](10,20,False)
            with patch('core.desktop.release_all'):
                self.assertEqual(self.call('/safety/kill_switch').status_code,200)
            saved=self.call('/macro/list').json()['result']
            self.assertEqual(saved[0]['event_count'],3)
            self.assertIsNone(macros.recording)

    def test_stop_interrupts_inflight_wait(self):
        self.select()
        result=[]
        def worker():
            try:
                rt.sleep(5)
            except Exception as exc:
                result.append(exc.status_code)
        thread=threading.Thread(target=worker);thread.start()
        start=time.monotonic()
        with patch('core.desktop.release_all'):
            self.assertEqual(self.call('/safety/kill_switch').status_code,200)
        thread.join(1)
        self.assertFalse(thread.is_alive())
        self.assertEqual(result,[409])
        self.assertLess(time.monotonic()-start,1)

    def test_missing_context_and_audit_errors(self):
        self.select()
        self.assertEqual(self.client.post('/keyboard/press',json={'key':'a'}).status_code,409)
        with patch('core.system_ops.system',side_effect=RuntimeError('internal test error')):
            self.assertEqual(self.call('/system/info').status_code,500)
        last=json.loads((rt.PRIVATE/'server.jsonl').read_text(encoding='utf-8').splitlines()[-1])
        self.assertIn('internal test error',last['error'])
        self.assertEqual(last['status'],500)


    def test_macro_verify_and_cancelled_question(self):
        self.select()
        rec=self.call('/macro/record',{'name':'verify'}).json()['result']
        self.call('/macro/stop')
        area={'left':0,'top':0,'width':4,'height':3}
        with patch('core.imaging.capture',side_effect=[(self.png('black'),area),(self.png('white'),area)]), patch('core.desktop.release_all'):
            result=self.call('/macro/replay_with_verify',{'macro_id':rec['id'],'verify':{'expect':'changed'}})
            self.assertEqual(result.status_code,200,result.text)
            self.assertTrue(result.json()['result']['verification']['passed'])
        q=self.call('/interaction/ask_user',{'question':'질문'}).json()['result']
        with patch('core.desktop.release_all'):
            self.call('/mission/cancel',{'reason':'사용자 취소'})
        self.assertEqual(self.call('/interaction/status',{'question_id':q['id']}).json()['result']['state'],'cancelled')
        self.assertEqual(self.call('/interaction/answer',{'question_id':q['id'],'answer':'늦은 답'},True).status_code,409)

    def test_no_capture_target_match_and_no_auto_retry(self):
        self.select()
        with patch('core.imaging.capture',side_effect=RuntimeError('capture failed')) as capture:
            self.assertEqual(self.call('/screen/screenshot',{'mode':'save'}).status_code,500)
            capture.assert_called_once()
        with patch('core.imaging.capture',return_value=(self.png('black'),{'left':0,'top':0,'width':4,'height':3})):
            a=self.call('/verify/hash').json()['result']['id']
        with patch('core.imaging.capture',return_value=(self.png('black'),{'left':5,'top':0,'width':4,'height':3})):
            b=self.call('/verify/hash').json()['result']['id']
        self.assertEqual(self.call('/verify/diff',{'mode':'saved','before_id':a,'after_id':b}).status_code,400)


if __name__=='__main__':unittest.main()
