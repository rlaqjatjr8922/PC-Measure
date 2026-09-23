import os
import platform
import subprocess
import time
from core import runtime as rt


def system(action, **kw):
    if action == 'status':
        import config
        return {'server': 'running', 'uptime': time.monotonic()-rt.started, 'stopped': rt.stop_event.is_set(),
                'mission_selected': rt.active is not None, 'bypass_hitl': config.BYPASS_HITL}
    if action == 'telemetry':
        return {**rt.stats, 'uptime': time.monotonic()-rt.started}
    if action == 'info':
        return {'os': platform.system(), 'release': platform.release(), 'architecture': platform.machine(),
                'python': platform.python_version(), 'cpu_count': os.cpu_count()}
    if action == 'processes':
        import psutil
        result = []
        for p in psutil.process_iter(['pid','name','status']):
            result.append(p.info)
        return result
    if action == 'clipboard':
        import win32clipboard as cb
        import win32con
        if kw['mode'] == 'write':
            rt.check_stop()
        cb.OpenClipboard()
        try:
            if kw['mode'] == 'read':
                return {'text': cb.GetClipboardData(win32con.CF_UNICODETEXT) if cb.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT) else ''}
            cb.EmptyClipboard()
            cb.SetClipboardText(str(kw['text']), win32con.CF_UNICODETEXT)
            return {'written': True}
        finally:
            cb.CloseClipboard()
    if action == 'start_app':
        rt.check_stop()
        from core.filesystem import checked
        executable = checked(kw['executable'])
        if not executable.is_file():
            rt.fail('실행 파일의 절대 경로를 지정하세요.', 404)
        args = kw['args']
        if not isinstance(args, list) or any(not isinstance(a,str) for a in args):
            rt.fail('args는 문자열 배열이어야 합니다.')
        proc = subprocess.Popen([str(executable), *args], shell=False, close_fds=True)
        return {'pid': proc.pid, 'started': True}
