import config
import ctypes
import json
import sqlite3
import secrets
from datetime import datetime, timezone
from contextlib import closing
try:
    ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
except (AttributeError, OSError):
    pass

def _gui():
    import pyautogui
    pyautogui.PAUSE = 0
    return pyautogui

def _release_all():
    if not config.held_keys and not config.held_buttons:
        return
    g = _gui()
    failures = []
    for key in tuple(config.held_keys):
        try:
            g._pyautogui_win._keyUp(key)
            config.held_keys.discard(key)
        except Exception as exc:
            failures.append(type(exc).__name__)
    for button in tuple(config.held_buttons):
        try:
            g._pyautogui_win._mouseUp(*g.position(), button)
            config.held_buttons.discard(button)
        except Exception as exc:
            failures.append(type(exc).__name__)
    if failures:
        raise RuntimeError(', '.join(failures))


def run(reason):
    config.stop_event.set()
    config.KILL_SWITCH = True
    release_error = None
    try:
        _release_all()
    except Exception as exc:
        release_error = type(exc).__name__
    config.PRIVATE.mkdir(parents=True, exist_ok=True)
    with config.lock, closing(sqlite3.connect(config.DB)) as db, db:
        db.execute('CREATE TABLE IF NOT EXISTS objects (kind TEXT, id TEXT, value TEXT, PRIMARY KEY(kind,id))')
        cancelled = 0
        for ident, raw in db.execute("SELECT id,value FROM objects WHERE kind='question'").fetchall():
            question = json.loads(raw)
            if question['state'] == 'pending':
                question['state'] = 'cancelled'
                db.execute("UPDATE objects SET value=? WHERE kind='question' AND id=?", (json.dumps(question, ensure_ascii=False), ident))
                cancelled += 1
        entry = {'id': secrets.token_hex(16), 'reason': reason, 'created_at': datetime.now(timezone.utc).isoformat(), 'input_release_error': release_error}
        db.execute('INSERT INTO objects VALUES (?,?,?)', ('stop', entry['id'], json.dumps(entry, ensure_ascii=False)))
    return {'stopped': True, 'reason': reason, 'input_release_error': release_error, 'cancelled_questions': cancelled}
