import config
import json
import sqlite3
import secrets
from contextlib import closing
from fastapi import HTTPException

def _delete(kind, ident):
    _get(kind, ident)
    with config.lock, closing(sqlite3.connect(config.DB)) as db, db:
        db.execute('DELETE FROM objects WHERE kind=? AND id=?', (kind, ident))

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

def _items(kind):
    _init()
    with closing(sqlite3.connect(config.DB)) as db:
        return [json.loads(row[0]) for row in db.execute('SELECT value FROM objects WHERE kind=? ORDER BY rowid', (kind,)).fetchall()]

def _number(value, minimum=None, maximum=None, integer=False):
    import math
    if isinstance(value, bool):
        _fail('숫자에 bool을 사용할 수 없습니다.')
    try:
        out = float(value)
    except (ValueError, TypeError):
        _fail('숫자 값이 필요합니다.')
    if not math.isfinite(out) or (integer and out != int(out)):
        _fail('유효한 숫자 값이 필요합니다.')
    if minimum is not None and out < minimum or (maximum is not None and out > maximum):
        _fail('숫자 값이 허용 범위를 벗어났습니다.')
    return int(out) if integer else out

def _options(value, allowed):
    if not isinstance(value, dict) or set(value) - set(allowed):
        _fail('options 값 또는 항목이 올바르지 않습니다.')
    return value

def _save(kind, item):
    _init()
    with config.lock, closing(sqlite3.connect(config.DB)) as db, db:
        db.execute('INSERT OR REPLACE INTO objects VALUES (?,?,?)', (kind, item['id'], json.dumps(item, ensure_ascii=False)))
    return item

def _uid():
    return secrets.token_hex(16)

def run(mode, **kw):
    if mode == 'list':
        _get('screenshot', kw['screenshot_id'])
        return [m for m in _items('marker') if m['screenshot_id'] == kw['screenshot_id']]
    with config.lock:
        if mode == 'add':
            s = _get('screenshot', kw['screenshot_id'])
            item = {'id': _uid(), 'screenshot_id': s['id']}
            item['marker_id'] = item['id']
        else:
            item = _get('marker', kw['marker_id'])
            s = _get('screenshot', item['screenshot_id'])
        if mode == 'delete':
            _delete('marker', item['id'])
            return {'deleted': True}
        if mode in ('add', 'update'):
            data = _options(kw['data'], {'x', 'y', 'annotation'})
            for axis, maximum in [('x', s['area']['width']), ('y', s['area']['height'])]:
                item[axis] = _number(data.get(axis, item.get(axis)), 0, maximum - 1, True)
            item['annotation'] = str(data.get('annotation', item.get('annotation', '')))
            return _save('marker', item)
        return item
