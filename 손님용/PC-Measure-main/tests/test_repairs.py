import ctypes
import time
from pathlib import Path
from unittest.mock import patch, MagicMock
import unittest
import test_features
from test_features import load
import config
import windows_input
import watch_engine
from fastapi import HTTPException

class Repairs(unittest.TestCase):
    setUp = test_features.Features.setUp
    request = test_features.Features.request

    def tearDown(self):
        watch_engine.shutdown()

    def wait_state(self, ident, expected):
        end=time.monotonic()+3
        while time.monotonic()<end:
            item=self.request('/watch/status',{'watch_id':ident})
            if item['state'] in expected:
                return item
            time.sleep(.02)
        self.fail(str(item))

    def test_watch_file_match_stop_timeout_and_validation(self):
        self.request('/watch/start',{'condition':'file_exists'},400)
        for opts in ({'interval':False},{'timeout':0},{'unknown':1}):
            self.request('/watch/start',{'condition':'file_exists','target':{'path':'temp:/watched'},'options':opts},400)
        args={'condition':'file_exists','target':{'path':'temp:/watched'},'options':{'interval':.05,'timeout':2}}
        item=self.request('/watch/start',args)
        self.request('/files/create',{'path':'temp:/watched','content':{'text':'ready'}})
        self.assertTrue(self.wait_state(item['id'],{'matched'})['matched'])
        args['condition']='file_changed'
        item=self.request('/watch/start',args)
        self.request('/files/edit',{'path':'temp:/watched','content':{'text':'different'}})
        self.wait_state(item['id'],{'matched'})
        args['condition']='file_exists';args['target']['path']='temp:/missing'
        item=self.request('/watch/start',args)
        self.assertEqual(self.request('/watch/stop',{'watch_id':item['id']})['state'],'stopped')
        args['options']['timeout']=.05
        item=self.request('/watch/start',args)
        self.wait_state(item['id'],{'timed_out'})
        self.assertEqual(len(self.request('/watch/list')),4)

    def test_watch_screen_default_window_and_kill(self):
        with patch('watch_engine.sample',side_effect=['a','b']):
            item=self.request('/watch/start')
            self.wait_state(item['id'],{'matched'})
        with patch('win32gui.IsWindow',return_value=True):
            item=self.request('/watch/start',{'condition':'window_exists','target':{'hwnd':1}})
            self.wait_state(item['id'],{'matched'})
        item=self.request('/watch/start',{'condition':'file_exists','target':{'path':'temp:/absent'},'options':{'interval':60}})
        config.stop_event.set()
        self.wait_state(item['id'],{'stopped'})
        config.stop_event.clear()
        self.assertFalse(watch_engine.workers)

    def test_system_names_and_hardlinks_preserve_file_protection(self):
        import os
        p=Path(self.temp.name)/'fake.exe';p.write_bytes(b'test')
        linked=p.with_name('linked.exe');os.link(p,linked)
        with patch('subprocess.Popen') as launch:
            launch.return_value.pid=123
            self.assertTrue(self.request('/system/start_app',{'executable':str(linked)})['started'])
            result=self.request('/system/start_app',{'executable':'calc.exe'})
            self.assertEqual(Path(result['executable']).name,'calc.exe')
            self.assertFalse(launch.call_args.kwargs['shell'])
        self.request('/files/read',{'path':str(linked)},403)
        for name in ('../fake.exe','fake.exe:stream','\\\\server\\file.exe'):
            r=self.client.post('/system/start_app',json={'executable':name})
            self.assertIn(r.status_code,(400,403))
        self.request('/system/start_app',{'executable':str(config.PRIVATE/'x.exe')},403)

    def test_mouse_virtual_desktop_sendinput_layout_and_denial(self):
        self.assertEqual(ctypes.sizeof(windows_input.INPUT),40 if ctypes.sizeof(ctypes.c_void_p)==8 else 28)
        def metrics(i):return {76:-1920,77:0,78:3840,79:1080}[i]
        events=[]
        def sent(count,pointer,size):
            e=ctypes.cast(pointer,ctypes.POINTER(windows_input.INPUT)).contents
            events.append((e.mi.dx,e.mi.dy,e.mi.dwFlags));return 1
        with patch.object(windows_input.user32,'GetSystemMetrics',side_effect=metrics),patch.object(windows_input.user32,'SendInput',side_effect=sent):
            windows_input.move_cursor(-1920,0);windows_input.move_cursor(1919,1079)
            self.assertEqual(events[0][2],0xC001)
            self.assertLess(events[0][0],30);self.assertGreater(events[1][0],65500)
            with self.assertRaises(HTTPException):windows_input.move_cursor(1920,0)
        with patch.object(windows_input.user32,'GetSystemMetrics',side_effect=metrics),patch.object(windows_input.user32,'SendInput',return_value=0):
            with self.assertRaises(HTTPException) as exc:windows_input.move_cursor(0,0)
            self.assertEqual(exc.exception.status_code,403)

    def test_mouse_five_routes_use_shared_move(self):
        for feature in ('click','double_click','right_click','hover','drag'):
            module=load('mouse',feature); gui=MagicMock();gui.position.return_value=(20,20)
            with patch.object(module,'_gui',return_value=gui),patch('windows_input.move_cursor') as move:
                module.run(x=30,y=40,start_x=20,start_y=20,end_x=30,end_y=40,options={'duration':0,'interval':0})
                self.assertTrue(move.called)
                self.assertFalse(config.held_buttons)

    def test_focus_recovers_and_detaches_on_denial(self):
        import win32gui as wg
        import win32process as wp
        with patch.object(wg,'GetForegroundWindow',return_value=2),patch.object(wg,'IsIconic',return_value=False),patch.object(wg,'SetForegroundWindow',side_effect=RuntimeError()),patch.object(wg,'BringWindowToTop'),patch.object(wp,'GetWindowThreadProcessId',return_value=(10,100)),patch('win32api.GetCurrentThreadId',return_value=20),patch.object(wp,'AttachThreadInput') as attach:
            with self.assertRaises(HTTPException) as exc:windows_input.focus_window(1)
            self.assertEqual(exc.exception.status_code,409)
            self.assertEqual(attach.call_args_list[-1].args,(20,10,False))
        with patch.object(wg,'GetForegroundWindow',side_effect=[2,1]),patch.object(wg,'IsIconic',return_value=False),patch.object(wg,'SetForegroundWindow'):
            windows_input.focus_window(1)
