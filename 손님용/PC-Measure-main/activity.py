"""Local operation journal and explicitly enabled physical-input recording."""
import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from contextlib import closing
import config

LOCK = threading.RLock()
LISTENERS = []
REPLAY_LOCK = threading.Lock()
RECORDING_ERROR = None

def now():
    return datetime.now(timezone.utc).isoformat()

def db():
    config.PRIVATE.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config.PRIVATE / 'activity.sqlite3', timeout=20)
    conn.execute('CREATE TABLE IF NOT EXISTS settings (id INTEGER PRIMARY KEY, value TEXT)')
    conn.execute('CREATE TABLE IF NOT EXISTS events (id TEXT PRIMARY KEY, time TEXT, value TEXT)')
    conn.execute('CREATE TABLE IF NOT EXISTS macros (id TEXT PRIMARY KEY, value TEXT)')
    return conn

def settings():
    with LOCK, closing(db()) as conn:
        row = conn.execute('SELECT value FROM settings WHERE id=1').fetchone()
    return json.loads(row[0]) if row else {'scope': 'program', 'screenshot': False}

def configure(scope=None, screenshot=None):
    with LOCK:
        value = settings()
        if scope is not None:
            if scope not in ('none', 'program', 'all'):
                raise ValueError('scope: none, program, all 중 선택하세요.')
            value['scope'] = scope
        if screenshot is not None:
            if type(screenshot) is not bool:
                raise ValueError('screenshot은 true/false입니다.')
            value['screenshot'] = screenshot
        # Querying configuration does not start a recorder.
        if scope is not None:
            stop_listeners()
            if scope == 'all':
                start_listeners()
        with closing(db()) as conn, conn:
            conn.execute('INSERT OR REPLACE INTO settings VALUES (1,?)', (json.dumps(value),))
        return {**value, 'human_recording': bool(LISTENERS), 'recording_error': RECORDING_ERROR}

def record(path, arguments, success, source='program', error=None, ident=None, event_time=None):
    with LOCK:
        value = settings()
        if value['scope'] == 'none' or (source == 'human' and value['scope'] != 'all'):
            return
        ident = ident or uuid.uuid4().hex
        item = dict(id=ident, time=event_time or now(), arguments=arguments, success=bool(success),
                    source=source, path=path, error=error)
        if value['screenshot']:
            try:
                from screen.screenshot import _capture
                raw, _ = _capture({})
                folder = config.DATA_DIR / 'activity-screenshots'
                folder.mkdir(parents=True, exist_ok=True)
                (folder / (ident + '.png')).write_bytes(raw)
                item['screenshot'] = str(folder / (ident + '.png'))
            except Exception as exc:
                item['screenshot_error'] = str(exc)
        with closing(db()) as conn, conn:
            conn.execute('INSERT INTO events VALUES (?,?,?)', (ident, item['time'], json.dumps(item, ensure_ascii=False)))
        return item

def timestamp(value):
    out = datetime.fromisoformat(value)
    if out.tzinfo is None:
        raise ValueError('시간에는 시간대가 필요합니다. 예: 2026-10-03T14:00:00+09:00')
    return out.astimezone(timezone.utc).isoformat()

def events(start=None, end=None, limit=200):
    limit = int(limit)
    if not 1 <= limit <= 10000:
        raise ValueError('limit은 1~10000입니다.')
    lo, hi = timestamp(start) if start else '', timestamp(end) if end else '9999'
    if lo > hi:
        raise ValueError('시작 시간이 종료 시간보다 늦습니다.')
    with LOCK, closing(db()) as conn:
        rows = conn.execute('SELECT value FROM events WHERE time>=? AND time<=? ORDER BY time DESC LIMIT ?', (lo, hi, limit)).fetchall()
    return {'logs': [json.loads(row[0]) for row in rows]}

def stop_listeners():
    for listener in LISTENERS:
        listener.stop()
    LISTENERS.clear()

def start_listeners():
    global RECORDING_ERROR
    RECORDING_ERROR = None
    from pynput import keyboard, mouse
    from queue import Queue
    queue = Queue(maxsize=10000)
    active = threading.Event()
    active.set()
    def enqueue(path, args):
        if active.is_set():
            try:
                queue.put_nowait((path, args, now()))
            except Exception:
                global RECORDING_ERROR
                RECORDING_ERROR = '기록 대기열이 가득 찼습니다. 일부 입력이 누락되었습니다.'
    def worker():
        while active.is_set():
            try:
                path, args, event_time = queue.get(timeout=.3)
            except Exception:
                continue
            try:
                record(path, args, True, 'human', event_time=event_time)
            except Exception as exc:
                global RECORDING_ERROR
                RECORDING_ERROR = str(exc)
    def key_filter(msg, data):
        # LLKHF_INJECTED: program-generated keys are logged as API operations.
        if not data.flags & 0x10:
            enqueue('/recording/input', {'kind': 'key', 'vk': int(data.vkCode), 'scan':int(data.scanCode), 'extended':bool(data.flags & 1), 'down': msg in (0x100, 0x104)})
        return False
    def mouse_filter(msg, data):
        if not data.flags & 1:
            enqueue('/recording/input', {'kind': 'mouse', 'message': int(msg), 'x': int(data.pt.x), 'y': int(data.pt.y), 'data': int(data.mouseData)})
        return False
    key_listener = keyboard.Listener(win32_event_filter=key_filter)
    mouse_listener = mouse.Listener(win32_event_filter=mouse_filter)
    class WorkerStop:
        def stop(self):
            active.clear()
    started = []
    try:
        for listener in (key_listener, mouse_listener):
            listener.start()
            listener.wait()
            started.append(listener)
        threading.Thread(target=worker, daemon=True).start()
        def indicator():
            import tkinter as tk
            panel = tk.Tk()
            panel.title('PC Measure · 입력 기록 중')
            panel.geometry('460x140')
            tk.Label(panel,text='마우스·키보드 입력을 기록하고 있습니다.',fg='#a02020').pack(pady=12)
            status = tk.StringVar(value='기록을 중지하려면 아래 버튼을 누르세요.')
            tk.Label(panel,textvariable=status,wraplength=430).pack()
            def stop():
                configure('none')
            tk.Button(panel,text='기록 중지',command=stop).pack(pady=8)
            panel.protocol('WM_DELETE_WINDOW',stop)
            def poll():
                if not active.is_set():
                    panel.destroy()
                    return
                if RECORDING_ERROR:
                    status.set(RECORDING_ERROR)
                panel.after(300,poll)
            poll()
            panel.mainloop()
        threading.Thread(target=indicator,daemon=True).start()
        LISTENERS.extend(started + [WorkerStop()])
    except Exception:
        active.clear()
        for listener in started:
            listener.stop()
        raise

def replay_input(arguments):
    import ctypes
    import time
    user = ctypes.windll.user32
    if arguments['kind'] == 'key':
        user.keybd_event(arguments['vk'], arguments.get('scan',0), (1 if arguments.get('extended') else 0) | (0 if arguments['down'] else 2), 0)
    else:
        user.SetCursorPos(arguments['x'], arguments['y'])
        msg = arguments['message']
        flag = {0x201:2, 0x202:4, 0x204:8, 0x205:16, 0x207:32, 0x208:64, 0x20B:0x80, 0x20C:0x100, 0x20A:0x800, 0x20E:0x1000}.get(msg)
        if flag:
            data = ctypes.c_short(arguments['data'] >> 16).value if msg in (0x20A, 0x20E) else arguments['data'] >> 16 if msg in (0x20B,0x20C) else 0
            user.mouse_event(flag, 0, 0, data, 0)
    return {'success': True}

def macro_create(title, start, end):
    if not isinstance(title, str) or not title.strip():
        raise ValueError('제목이 필요합니다.')
    rows = events(start, end, 10000)['logs']
    if len(rows) == 10000:
        raise ValueError('기록이 너무 많습니다. 시간 범위를 줄여 주세요.')
    rows = [row for row in reversed(rows) if row['success'] and not row['path'].startswith(('/macro/', '/recording/config', '/recording/list'))]
    if not rows:
        raise ValueError('해당 구간에 재생 가능한 기록이 없습니다.')
    item = dict(id=uuid.uuid4().hex, title=title.strip(), start=start, end=end, created_at=now(), steps=rows)
    with LOCK, closing(db()) as conn, conn:
        conn.execute('INSERT INTO macros VALUES (?,?)', (item['id'], json.dumps(item, ensure_ascii=False)))
    return {k:v for k,v in item.items() if k != 'steps'} | {'count':len(rows)}

def macro_list():
    with LOCK, closing(db()) as conn:
        items = [json.loads(row[0]) for row in conn.execute('SELECT value FROM macros')]
    return {'macros': [{k:v for k,v in item.items() if k != 'steps'} | {'count':len(item['steps'])} for item in items]}

def macro_run(macro_id):
    import time
    import server
    if not REPLAY_LOCK.acquire(blocking=False):
        raise ValueError('이미 매크로가 실행 중입니다.')
    pressed = set()
    buttons = set()
    try:
        with LOCK, closing(db()) as conn:
            row = conn.execute('SELECT value FROM macros WHERE id=?', (macro_id,)).fetchone()
        if not row:
            raise ValueError('매크로 ID를 찾을 수 없습니다.')
        item = json.loads(row[0])
        first = datetime.fromisoformat(item['steps'][0]['time'])
        replay_started = time.monotonic()
        count = 0
        for step in item['steps']:
            current = datetime.fromisoformat(step['time'])
            delay = max(0, (current-first).total_seconds() - (time.monotonic()-replay_started))
            if config.stop_event.wait(delay) or config.KILL_SWITCH:
                raise ValueError('긴급 중지로 매크로가 중단되었습니다.')
            if step['path'] == '/recording/input':
                args = step['arguments']
                if args['kind'] == 'key':
                    if args['down']: pressed.add(args['vk'])
                    else: pressed.discard(args['vk'])
                else:
                    msg=args['message']
                    if msg in (0x201,0x204,0x207): buttons.add(msg)
                    elif msg in (0x202,0x205,0x208): buttons.discard(msg-1)
                replay_input(args)
                record('/recording/input',args,True,'program')
            else:
                group, feature = step['path'].strip('/').split('/')
                result = server.execute(group, feature, step['arguments'])
                if isinstance(result,dict) and result.get('success') is False:
                    raise ValueError('매크로 단계 실행 실패')
            count += 1
        return {'success':True, 'id':macro_id, 'title':item['title'], 'executed':count}
    finally:
        # A range may end after keyDown or a failing step. Release program-held
        # inputs as well as physical-input replay state before returning.
        try:
            from input.keyboard import _release_all
            if config.held_keys or config.held_buttons:
                _release_all()
        except Exception:
            pass
        if pressed:
            import ctypes
            for key in pressed:
                ctypes.windll.user32.keybd_event(key,0,2,0)
        if buttons:
            import ctypes
            for button in buttons:
                ctypes.windll.user32.mouse_event({0x201:4,0x204:16,0x207:64}[button],0,0,0,0)
        REPLAY_LOCK.release()
