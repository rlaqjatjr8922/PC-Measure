"""Shared persistence and execution state; no planning or automatic recovery."""
import contextvars
from contextlib import closing
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import secrets
import sqlite3
import threading
import time
from fastapi import HTTPException
import config

BASE = Path(__file__).resolve().parents[1]
PRIVATE = BASE / '.private'
DATA = BASE / 'data'
DB = PRIVATE / 'state.sqlite3'
lock = threading.RLock()
input_lock = threading.RLock()
stop_event = threading.Event()
context = contextvars.ContextVar('mission_context', default=None)
active = None
started = time.monotonic()
stats = {'requests': 0, 'errors': 0, 'duration_ms': 0}
held_keys = set()
held_buttons = set()


def fail(message, status=400):
    raise HTTPException(status, message)


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def uid():
    return secrets.token_hex(16)


def init():
    PRIVATE.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(DB)) as db, db:
        db.execute('CREATE TABLE IF NOT EXISTS objects (kind TEXT, id TEXT, mission TEXT, value TEXT, PRIMARY KEY(kind,id))')
    path = PRIVATE / 'user.key'
    if not path.exists():
        try:
            with path.open('x', encoding='utf-8') as f:
                f.write(secrets.token_urlsafe(32))
        except FileExistsError:
            pass


def user_key():
    init()
    return (PRIVATE / 'user.key').read_text(encoding='utf-8')


def save(kind, item, mission=None):
    init()
    if mission is not None:
        item = {**item, 'mission_id': mission}
    with lock, closing(sqlite3.connect(DB)) as db, db:
        db.execute('INSERT OR REPLACE INTO objects VALUES (?,?,?,?)',
                   (kind, item['id'], mission, json.dumps(item, ensure_ascii=False)))
    return item


def get(kind, ident, scoped=True):
    init()
    with closing(sqlite3.connect(DB)) as db:
        row = db.execute('SELECT mission,value FROM objects WHERE kind=? AND id=?', (kind, str(ident))).fetchone()
    if not row:
        fail('대상을 찾을 수 없습니다.', 404)
    if scoped and row[0] != current()['id']:
        fail('현재 Mission의 데이터만 사용할 수 있습니다.', 403)
    return json.loads(row[1])


def items(kind, scoped=True):
    init()
    with closing(sqlite3.connect(DB)) as db:
        rows = db.execute('SELECT value FROM objects WHERE kind=?' + (' AND mission=?' if scoped else '') + ' ORDER BY rowid',
                          (kind, current()['id']) if scoped else (kind,)).fetchall()
    return [json.loads(row[0]) for row in rows]


def delete(kind, ident):
    get(kind, ident)
    with lock, closing(sqlite3.connect(DB)) as db, db:
        db.execute('DELETE FROM objects WHERE kind=? AND id=?', (kind, ident))


def current():
    chosen = context.get() or active
    if chosen is None:
        fail('사용자가 먼저 Mission을 선택해야 합니다.', 409)
    if active is None or chosen['generation'] != active['generation']:
        fail('이전 Mission 연결은 더 이상 유효하지 않습니다.', 409)
    return get('mission', chosen['id'], scoped=False)


def check_stop():
    if stop_event.is_set() or config.KILL_SWITCH:
        fail('KILL_SWITCH: 자동 작업이 중지되었습니다.', 409)
    if context.get() is not None:
        m = current()
        if m['state'] == 'cancelled':
            fail('현재 Mission이 중단되었습니다.', 409)


def sleep(seconds):
    seconds = number(seconds, 0, 3600)
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        check_stop()
        stop_event.wait(min(.02, end - time.monotonic()))
    check_stop()


def number(value, minimum=None, maximum=None, integer=False):
    import math
    if isinstance(value, bool):
        fail('숫자에 bool을 사용할 수 없습니다.')
    try:
        out = float(value)
    except (ValueError, TypeError):
        fail('숫자 값이 필요합니다.')
    if not math.isfinite(out) or (integer and out != int(out)):
        fail('유효한 숫자 값이 필요합니다.')
    if minimum is not None and out < minimum or maximum is not None and out > maximum:
        fail('숫자 값이 허용 범위를 벗어났습니다.')
    return int(out) if integer else out


def options(value, allowed):
    if not isinstance(value, dict) or set(value) - set(allowed):
        fail('options 값 또는 항목이 올바르지 않습니다.')
    return value


def mission_dir():
    path = DATA / 'missions' / current()['id']
    path.mkdir(parents=True, exist_ok=True)
    return path


def log_work(entry):
    m = current()
    return save('work_log', {**entry, 'id': uid(), 'mission_id': m['id'], 'created_at': timestamp()}, m['id'])


def stop(reason):
    stop_event.set()
    config.KILL_SWITCH = True
    from core import macros
    if macros.recording:
        macros.finish()
    # State is set before acquiring any input lock. Current action releases its held inputs.
    release_error = None
    try:
        from core.desktop import release_all
        release_all()
    except Exception as exc:
        release_error = type(exc).__name__
    with lock:
        if active:
            m = get('mission', active['id'], scoped=False)
            m.update(state='cancelled', cancel_reason=reason, updated_at=timestamp())
            save('mission', m)
            save('work_log', {'id': uid(), 'mission_id': m['id'], 'created_at': timestamp(), 'cancel_reason': reason}, m['id'])
            for question in items('question', scoped=False):
                if question.get('mission_id') == m['id'] and question['state'] == 'pending':
                    question['state'] = 'cancelled'
                    save('question', question, m['id'])
    return {'stopped': True, 'reason': reason, 'input_release_error': release_error}
