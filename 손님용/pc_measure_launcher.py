"""Standalone visible launcher for the PC Measure server and Cloudflare tunnel."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import queue
import re
import socket
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import httpx
import uvicorn
import config
import api_config
import server

BUNDLE = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
RUNTIME = Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'PCMeasure'
GROUPS = [g for g, value in vars(api_config).items() if not g.startswith('_') and isinstance(value, dict)]

class Runtime:
    def __init__(self, folder, emit=print):
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)
        self.emit = emit
        self.stop = threading.Event()
        self.service = None
        self.thread = None
        self.tunnel = None
        self.sock = None
        self.log = None
        config.DATA_DIR = self.folder / 'data'
        config.PRIVATE = self.folder / '.private'
        config.DB = config.PRIVATE / 'feature-state.sqlite3'
        config.KILL_SWITCH = False
        config.stop_event.clear()

    def start_server(self, ephemeral=False):
        self.sock = socket.socket()
        try:
            self.sock.bind(('127.0.0.1', 0 if ephemeral else config.PORT))
        except OSError:
            self.sock.close()
            self.sock = socket.socket()
            self.sock.bind(('127.0.0.1', 0))
        port = self.sock.getsockname()[1]
        self.local = f'http://127.0.0.1:{port}'
        self.service = uvicorn.Server(uvicorn.Config(server.app, host='127.0.0.1', port=port, log_config=None, access_log=False))
        self.thread = threading.Thread(target=self.service.run, kwargs={'sockets': [self.sock]}, daemon=True)
        self.thread.start()
        for _ in range(100):
            if self.stop.is_set(): raise RuntimeError('Stopped')
            if self.service.started: break
            if not self.thread.is_alive(): raise RuntimeError('Server failed to start')
            time.sleep(.1)
        if not self.service.started: raise RuntimeError('Server startup timed out')
        if not self.healthy(self.local): raise RuntimeError('Local status check failed')
        self.emit('Server ready: ' + self.local)

    @staticmethod
    def healthy(base):
        try:
            r = httpx.get(base + '/system/status', timeout=4)
            v = r.json()
            return r.status_code == 200 and v.get('success') is True and v.get('result', {}).get('server') == 'running'
        except Exception:
            return False

    def start_tunnel(self):
        binary = BUNDLE / 'cloudflared.exe'
        if not binary.is_file(): raise RuntimeError('Bundled cloudflared.exe missing')
        self.log_path = self.folder / 'cloudflared.log'
        self.log = self.log_path.open('w', encoding='utf-8')
        self.tunnel = subprocess.Popen([str(binary), 'tunnel', '--url', self.local, '--no-autoupdate'], stdout=self.log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
        self.emit('Creating public URL...')
        public = None
        for _ in range(120):
            if self.stop.wait(1): raise RuntimeError('Stopped')
            if self.tunnel.poll() is not None: raise RuntimeError('Cloudflare stopped; see cloudflared.log')
            content = self.log_path.read_text(encoding='utf-8', errors='replace')
            match = re.search(r'https://[a-z0-9-]+\.trycloudflare\.com', content)
            if match:
                public = match.group(0)
                break
        if not public: raise RuntimeError('Cloudflare URL timed out')
        self.emit('Checking: ' + public)
        for _ in range(60):
            if self.stop.is_set(): raise RuntimeError('Stopped')
            if self.tunnel.poll() is not None: raise RuntimeError('Cloudflare tunnel exited')
            if self.healthy(public):
                self.emit('Public URL ready: ' + public)
                return public
            self.stop.wait(2)
        raise RuntimeError('Public URL did not become reachable')

    def close(self):
        self.stop.set()
        import activity
        activity.stop_listeners()
        if self.tunnel and self.tunnel.poll() is None:
            self.tunnel.terminate()
            try: self.tunnel.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.tunnel.kill(); self.tunnel.wait(timeout=5)
        if self.service: self.service.should_exit = True
        if self.thread: self.thread.join(timeout=5)
        if self.sock: self.sock.close()
        if self.log: self.log.close()


def smoke_test(report_path, tunnel=False):
    report = {'success': False, 'frozen': bool(getattr(sys, 'frozen', False))}
    with tempfile.TemporaryDirectory(prefix='PCMeasure-exe-test-') as folder:
        runtime = Runtime(folder, lambda _: None)
        try:
            # Import every dynamically loaded API module from the bundle.
            count = 0
            for group in GROUPS:
                for feature in getattr(api_config, group):
                    path = BUNDLE / group / (feature + '.py')
                    spec = importlib.util.spec_from_file_location('smoke_' + group + '_' + feature, path)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    assert callable(module.run)
                    count += 1
            # Exercise dependencies that API modules import only when called.
            import pyautogui, mss, mss.tools, psutil, win32gui, win32process, win32clipboard, win32con
            from PIL import Image, ImageChops, ImageStat
            runtime.start_server(ephemeral=True)
            with httpx.Client(base_url=runtime.local, timeout=10, trust_env=False) as client:
                def call(path, data):
                    r = client.post(path, json=data)
                    assert r.status_code == 200, (path, r.status_code)
                    return r.json()['result']
                call('/files/create', {'path': 'temp:/check', 'kind': 'directory'})
                call('/files/save', {'path': 'temp:/check/test.txt', 'content': {'text': 'EXE 한글'}})
                assert call('/files/read', {'path': 'temp:/check/test.txt'})['content'] == 'EXE 한글'
                call('/files/copy', {'path': 'temp:/check', 'destination': 'temp:/copy', 'options': {'recursive': True}})
                call('/files/delete', {'path': 'temp:/check', 'options': {'recursive': True}})
                call('/files/delete', {'path': 'temp:/copy', 'options': {'recursive': True}})
                watch = call('/watch/start', {'condition': 'file_exists', 'target': {'path': 'temp:/watch-ready'}, 'options': {'interval': .05, 'timeout': 3}})
                call('/files/create', {'path': 'temp:/watch-ready', 'content': {'text': 'ready'}})
                for _ in range(40):
                    state = call('/watch/status', {'watch_id': watch['id']})
                    if state['state'] == 'matched': break
                    time.sleep(.05)
                assert state['state'] == 'matched', state
                assert call('/watch/list', {})
                stopped = call('/watch/start', {'condition': 'file_exists', 'target': {'path': 'temp:/never'}, 'options': {'interval': .05}})
                assert call('/watch/stop', {'watch_id': stopped['id']})['state'] == 'stopped'
                call('/files/delete', {'path': 'temp:/watch-ready'})
                report['watch_lifecycle'] = True

            version = subprocess.run([str(BUNDLE / 'cloudflared.exe'), '--version'], capture_output=True, text=True, timeout=15, creationflags=subprocess.CREATE_NO_WINDOW, check=True).stdout.strip()
            report.update(api_modules=count, local_http=True, file_lifecycle=True, cloudflared=version)
            if tunnel:
                report['public_url'] = runtime.start_tunnel()
                report['public_http'] = True
            report['success'] = True
        except Exception:
            report['error'] = traceback.format_exc()
        finally:
            runtime.close()
    Path(report_path).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return 0 if report['success'] else 1


def gui():
    import tkinter as tk
    from tkinter.scrolledtext import ScrolledText
    root = tk.Tk()
    root.title('PC Measure')
    root.geometry('695x430')
    messages = queue.Queue()
    runtime = Runtime(RUNTIME, messages.put)
    tk.Label(root, text='PC Measure 서버 · Cloudflare · Discord', font=('', 15)).pack(pady=12)
    status = tk.StringVar(value='서버를 시작하는 중입니다…')
    tk.Label(root, textvariable=status, fg='#003366').pack(pady=5)
    import activity
    text = ScrolledText(root, height=15, state='disabled')
    text.pack(fill='both', expand=True, padx=15, pady=10)
    finished = threading.Event()
    def worker():
        try:
            runtime.start_server()
            public = runtime.start_tunnel()
            settings = json.loads((BUNDLE / 'launcher_settings.json').read_text(encoding='utf-8'))
            response = httpx.post(settings['webhook_url'] + '?wait=true', json={'content': '0001 ' + public, 'allowed_mentions': {'parse': []}}, timeout=30)
            if not response.is_success: raise RuntimeError('Discord returned HTTP ' + str(response.status_code))
            messages.put('Discord 전송 완료: 0001 ' + public)
            messages.put('실행 중입니다. 종료 버튼을 누르면 서버와 터널을 종료합니다.')
            while not runtime.stop.wait(1):
                if not runtime.thread.is_alive(): raise RuntimeError('Server stopped')
                if runtime.tunnel.poll() is not None: raise RuntimeError('Cloudflare stopped')
        except Exception as exc:
            if not runtime.stop.is_set():
                messages.put('오류: ' + str(exc))
                (RUNTIME / 'launcher-error.log').write_text(traceback.format_exc(), encoding='utf-8')
        finally:
            runtime.close(); finished.set()
    def poll():
        while not messages.empty():
            line = messages.get()
            status.set(line)
            text.configure(state='normal'); text.insert('end', line + '\n'); text.see('end'); text.configure(state='disabled')
        root.after(150, poll)
    def closing():
        runtime.stop.set()
        status.set('서버와 터널을 종료하는 중입니다…')
        if finished.is_set(): root.destroy()
        else: root.after(150, closing)
    tk.Button(root, text='종료', command=closing, width=15).pack(pady=8)
    root.protocol('WM_DELETE_WINDOW', closing)
    threading.Thread(target=worker, daemon=True).start()
    poll(); root.mainloop()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--smoke-test', metavar='REPORT')
    parser.add_argument('--test-tunnel', action='store_true')
    options = parser.parse_args()
    if options.smoke_test:
        raise SystemExit(smoke_test(options.smoke_test, options.test_tunnel))
    gui()
