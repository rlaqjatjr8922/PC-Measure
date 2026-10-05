"""Bounded, read-only watches with durable status and cancellable workers."""
import copy
import json
import math
import secrets
import sqlite3
import threading
import time
from contextlib import closing
from datetime import datetime, timezone
from fastapi import HTTPException
import config

workers = {}
lock = threading.RLock()

def now():
    return datetime.now(timezone.utc).isoformat()

def database():
    config.PRIVATE.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(config.DB)
    db.execute('CREATE TABLE IF NOT EXISTS objects (kind TEXT, id TEXT, value TEXT, PRIMARY KEY(kind,id))')
    return db

def save(item):
    with closing(database()) as db, db:
        db.execute('INSERT OR REPLACE INTO objects VALUES (?,?,?)', ('watch', item['id'], json.dumps(item, ensure_ascii=False)))
    return item

def get(watch_id):
    with lock, closing(database()) as db:
        row = db.execute("SELECT value FROM objects WHERE kind='watch' AND id=?", (watch_id,)).fetchone()
        if not row:
            raise HTTPException(404, 'Watch를 찾을 수 없습니다.')
        item = json.loads(row[0])
        if item['state'] == 'running' and watch_id not in workers:
            item.update(state='stopped', reason='server_restarted', ended_at=now())
            save(item)
        return item

def listing():
    with lock, closing(database()) as db:
        ids = [r[0] for r in db.execute("SELECT id FROM objects WHERE kind='watch' ORDER BY rowid")]
        return [get(i) for i in ids]

def sample(condition, target):
    if condition == 'screen_changed':
        from verify.hash import _capture, _image_hash
        raw, _ = _capture(target)
        return _image_hash(raw)
    if condition.startswith('file_'):
        from files.info import _checked
        p = _checked(target['path'])
        if condition == 'file_exists':
            return p.exists()
        if not p.exists():
            return None
        stat = p.stat()
        return [stat.st_mtime_ns, stat.st_size]
    import win32gui
    return bool(win32gui.IsWindow(target['hwnd']))

def number(value, minimum, maximum):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not minimum <= value <= maximum:
        raise HTTPException(400, 'Watch 시간 값이 허용 범위를 벗어났습니다.')
    return float(value)

def start(condition='screen_changed', target=None, options=None):
    target = copy.deepcopy({} if target is None else target)
    options = {} if options is None else options
    if condition not in ('screen_changed', 'file_exists', 'file_changed', 'window_exists'):
        raise HTTPException(400, 'condition: screen_changed, file_exists, file_changed, window_exists 중 선택하세요.')
    if not isinstance(target, dict) or not isinstance(options, dict) or set(options) - {'interval', 'timeout'}:
        raise HTTPException(400, 'Watch target/options가 올바르지 않습니다.')
    if condition.startswith('file_') and (set(target) != {'path'} or not isinstance(target.get('path'), str) or not target['path']):
        raise HTTPException(400, '파일 Watch에는 target.path가 필요합니다.')
    if condition == 'window_exists' and (set(target) != {'hwnd'} or type(target.get('hwnd')) is not int or target['hwnd'] <= 0):
        raise HTTPException(400, '창 Watch에는 양의 정수 target.hwnd가 필요합니다.')
    interval = number(options.get('interval', 1), .05, 60)
    timeout = number(options.get('timeout', 300), .05, 86400)
    with lock:
        if config.stop_event.is_set() or config.KILL_SWITCH:
            raise HTTPException(409, 'KILL_SWITCH: 작업이 중지되었습니다.')
        if len(workers) >= 16:
            raise HTTPException(409, '동시에 최대 16개 Watch를 실행할 수 있습니다.')
        baseline = sample(condition, target)
        ident = secrets.token_hex(16)
        item = dict(id=ident, watch_id=ident, condition=condition, target=target,
                    options=dict(interval=interval, timeout=timeout), state='running',
                    matched=False, created_at=now(), checks=0)
        save(item)
        cancel = threading.Event()
        thread = threading.Thread(target=monitor, args=(item, baseline, cancel), daemon=True)
        workers[ident] = (cancel, thread)
        thread.start()
        return copy.deepcopy(item)

def monitor(item, baseline, cancel):
    deadline = time.monotonic() + item['options']['timeout']
    try:
        while True:
            with lock:
                if cancel.is_set() or config.stop_event.is_set() or config.KILL_SWITCH:
                    item.update(state='stopped', reason='cancelled')
                    break
                if time.monotonic() >= deadline:
                    item.update(state='timed_out')
                    break
            value = sample(item['condition'], item['target'])
            matched = bool(value) if item['condition'].endswith('_exists') else value != baseline
            with lock:
                # Do not publish a match after stop was accepted.
                if cancel.is_set() or config.stop_event.is_set() or config.KILL_SWITCH:
                    item.update(state='stopped', reason='cancelled')
                    break
                item.update(checks=item['checks']+1, checked_at=now(), matched=matched)
                if matched:
                    item.update(state='matched')
                    break
                save(item)
            remaining = min(item['options']['interval'], max(0, deadline-time.monotonic()))
            # Prompt kill-switch response, including with a long polling interval.
            end = time.monotonic() + remaining
            while time.monotonic() < end and not config.stop_event.is_set():
                if cancel.wait(min(.1, max(0, end-time.monotonic()))):
                    break
    except Exception as exc:
        item.update(state='error', error=str(getattr(exc, 'detail', type(exc).__name__)))
    finally:
        with lock:
            item['ended_at'] = now()
            save(item)
            workers.pop(item['id'], None)

def stop(watch_id):
    with lock:
        item = get(watch_id)
        worker = workers.get(watch_id)
        if worker:
            worker[0].set()
    if worker:
        worker[1].join(timeout=5)
        if worker[1].is_alive():
            raise HTTPException(409, 'WATCH_STOP_PENDING: 현재 검사가 끝나면 중지됩니다.')
    return get(watch_id)

def shutdown():
    with lock:
        active = list(workers.values())
        for event, thread in active:
            event.set()
    for event, thread in active:
        thread.join(timeout=5)
