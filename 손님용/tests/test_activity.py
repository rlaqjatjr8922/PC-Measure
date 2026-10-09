import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import activity
import config
import server
from fastapi.testclient import TestClient

class ActivityTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        for key,value in {'PRIVATE':Path(temp.name)/'private','DATA_DIR':Path(temp.name)/'data'}.items():
            p=patch.object(config,key,value);p.start();self.addCleanup(p.stop)
        self.client=TestClient(server.app)
        self.addCleanup(self.client.close)
        config.KILL_SWITCH=False
        config.stop_event.clear()

    def test_scope_and_required_fields(self):
        activity.configure('none')
        activity.record('/mouse/click',{'x':1,'y':2},True)
        self.assertEqual(activity.events()['logs'],[])
        activity.configure('program')
        activity.record('/recording/input',{},True,'human')
        self.assertEqual(activity.events()['logs'],[])
        item=activity.record('/mouse/click',{'x':1,'y':2},False,error='failed')
        self.assertTrue({'id','time','arguments','success'} <= set(item))
        self.assertFalse(item['success'])
        self.assertEqual(len(activity.events()['logs']),1)

    def test_all_and_stop(self):
        with patch('activity.start_listeners') as start, patch('activity.stop_listeners') as stop:
            activity.configure('all')
            start.assert_called_once()
            activity.record('/recording/input',{'kind':'key','vk':65,'down':True},True,'human')
            self.assertEqual(len(activity.events()['logs']),1)
            activity.configure('none')
            self.assertGreaterEqual(stop.call_count,2)

    def test_http_errors_recorded(self):
        response=self.client.post('/mouse/click',json={'x':1})
        self.assertEqual(response.status_code,400)
        row=activity.events()['logs'][0]
        self.assertFalse(row['success'])
        self.assertEqual(row['arguments'],{'x':1})

    def test_screenshot_optional(self):
        with patch('screen.screenshot._capture',return_value=(b'PNG',{})) as capture:
            activity.configure('program',False)
            activity.record('/test/a',{},True)
            capture.assert_not_called()
            activity.configure(screenshot=True)
            item=activity.record('/test/a',{},True)
            self.assertTrue(Path(item['screenshot']).exists())

    def test_macro_creation_and_replay(self):
        activity.record('/mouse/click',{'x':1,'y':2},True,event_time='2026-10-03T01:00:00+00:00')
        activity.record('/mouse/click',{'x':8,'y':9},False,event_time='2026-10-03T01:00:01+00:00')
        result=activity.macro_create('선택한 작업','2026-10-03T10:00:00+09:00','2026-10-03T10:00:02+09:00')
        self.assertEqual(result['count'],1)
        self.assertEqual(activity.macro_list()['macros'][0]['title'],'선택한 작업')
        with patch('server.execute',return_value={'success':True}) as call:
            output=activity.macro_run(result['id'])
            call.assert_called_once_with('mouse','click',{'x':1,'y':2})
            self.assertEqual(output['executed'],1)
        config.stop_event.set()
        with patch('server.execute') as call:
            with self.assertRaises(ValueError):activity.macro_run(result['id'])
            call.assert_not_called()
        config.stop_event.clear()

    def test_empty_invalid_range(self):
        with self.assertRaises(ValueError):activity.macro_create('a','2026-10-03T01:00:00','2026-10-03T02:00:00')
        with self.assertRaises(ValueError):activity.macro_create('a','2026-10-03T01:00:00+00:00','2026-10-03T00:00:00+00:00')

    def test_query_does_not_enable_hooks(self):
        with patch('activity.start_listeners') as start:
            r=self.client.post('/recording/config',json={})
            self.assertEqual(r.status_code,200)
            start.assert_not_called()

    def test_powershell_validation_and_normal(self):
        module=server._execute
        with patch('ctypes.windll.shell32.IsUserAnAdmin',return_value=0):
            result=module('system','powershell',{'command':"[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; Write-Output 'hello'",'privilege':'normal'})
            self.assertTrue(result['success'])
            self.assertIn('hello',result['stdout'])
        with patch('ctypes.windll.shell32.IsUserAnAdmin',return_value=1):
            with self.assertRaises(PermissionError):module('system','powershell',{'command':'echo test','privilege':'normal'})

    def test_powershell_failure_and_admin_cancel(self):
        with patch('ctypes.windll.shell32.IsUserAnAdmin',return_value=0):
            result=server._execute('system','powershell',{'command':"throw 'expected test failure'",'privilege':'normal'})
            self.assertFalse(result['success'])
            self.assertNotEqual(result['exit_code'],0)
            self.assertIn('expected test failure',result['stderr'])
            with patch('subprocess.run') as run:
                from fastapi import HTTPException
                with self.assertRaises(HTTPException) as error:
                    server._execute('system','powershell',{'command':'echo test','privilege':'admin'})
                self.assertEqual(error.exception.status_code,403)
                self.assertIn('ADMIN_LAUNCH_FAILED',error.exception.detail)
                self.assertIn('-Verb RunAs',run.call_args.args[0][-1])

if __name__=='__main__':unittest.main()
