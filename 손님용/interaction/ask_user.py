import config
import json
import sqlite3
import secrets
from contextlib import closing
from datetime import datetime, timezone
from fastapi import HTTPException

def _check_stop():
    if config.stop_event.is_set() or config.KILL_SWITCH:
        _fail('KILL_SWITCH: 작업이 중지되었습니다. 서버를 재시작하세요.', 409)

def _fail(message, status=400):
    raise HTTPException(status, message)

def _init():
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    config.PRIVATE.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(config.DB)) as db, db:
        db.execute('CREATE TABLE IF NOT EXISTS objects (kind TEXT, id TEXT, value TEXT, PRIMARY KEY(kind,id))')

def _save(kind, item):
    _init()
    with config.lock, closing(sqlite3.connect(config.DB)) as db, db:
        db.execute('INSERT OR REPLACE INTO objects VALUES (?,?,?)', (kind, item['id'], json.dumps(item, ensure_ascii=False)))
    return item

def _timestamp():
    return datetime.now(timezone.utc).isoformat()

def _uid():
    return secrets.token_hex(16)

def run(**kw):
    with config.lock:
        _check_stop()
        if not isinstance(kw['question'], str) or not isinstance(kw['options'], list) or any((not isinstance(v, str) for v in kw['options'])):
            _fail('question은 문자열, options는 문자열 배열이어야 합니다.')
        q = _save('question', {'id': _uid(), 'question': kw['question'], 'options': kw['options'], 'state': 'pending', 'answer': None, 'created_at': _timestamp()})
        return q
