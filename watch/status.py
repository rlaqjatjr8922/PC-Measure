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

def run(**kw):
    item = _get('watch', kw['watch_id'])
    return item
