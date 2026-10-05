import config
import json
import sqlite3
from contextlib import closing

def _init():
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    config.PRIVATE.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(config.DB)) as db, db:
        db.execute('CREATE TABLE IF NOT EXISTS objects (kind TEXT, id TEXT, value TEXT, PRIMARY KEY(kind,id))')

def _items(kind):
    _init()
    with closing(sqlite3.connect(config.DB)) as db:
        return [json.loads(row[0]) for row in db.execute('SELECT value FROM objects WHERE kind=? ORDER BY rowid', (kind,)).fetchall()]

def run(**kw):
    return _items('question')
