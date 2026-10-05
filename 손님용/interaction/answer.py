import config
import json
import sqlite3
from contextlib import closing
from fastapi import HTTPException

def _fail(message, status=400):
    raise HTTPException(status, message)

def _get(kind, ident):
    _init()
    with closing(sqlite3.connect(config.DB)) as db:
        row = db.execute('SELECT value FROM objects WHERE kind=? AND id=?', (kind, str(ident))).fetchone()
    if not row:
        _fail('대상을 찾을 수 없습니다.', 404)
    return json.loads(row[0])

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

def run(**kw):
    with config.lock:
        q = _get('question', kw['question_id'])
        if config.stop_event.is_set() or config.KILL_SWITCH:
            if q['state'] == 'pending':
                q['state'] = 'cancelled'
                _save('question', q)
            _fail('중지된 상태에서는 답변할 수 없습니다.', 409)
        if q['state'] != 'pending':
            _fail('이미 종료된 질문입니다.', 409)
        q.update(answer=kw['answer'], state='answered')
        _save('question', q)
        return q
