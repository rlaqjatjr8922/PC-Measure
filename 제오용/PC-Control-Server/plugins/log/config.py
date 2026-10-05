import json
import re
import os
import uuid
from datetime import datetime, timezone, timedelta
from threading import RLock
import config

LOCK = RLock()
DEFAULT_LOG = dict(enabled=True, save_request=True, save_response=True,
                   save_error=True, save_reject=True, max_days=30)

def now():
    return datetime.now(timezone.utc).isoformat()

def read(path, default=None):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))

def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)

def log_config():
    return {**DEFAULT_LOG, **read(config.DATA_DIR / 'log_config.json', {})}

def prune(settings):
    cutoff = datetime.now(timezone.utc) - timedelta(days=settings['max_days'])
    for path in config.LOG_DIR.glob('*.json'):
        try:
            timestamp = datetime.fromisoformat(read(path)['timestamp'])
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=timezone.utc)
            if timestamp < cutoff:
                path.unlink()
        except (ValueError, KeyError, TypeError):
            continue

def log(kind, payload, mission_id=None, path=None):
    with LOCK:
        settings = log_config()
        prune(settings)
        if not settings['enabled'] or not settings['save_' + kind]:
            return
        entry = dict(id=uuid.uuid4().hex, timestamp=now(), type=kind,
                     mission_id=mission_id, path=path, data=payload)
        write(config.LOG_DIR / (entry['id'] + '.json'), entry)

def run(**values):
    settings = {**log_config(), **values}
    write(config.DATA_DIR / 'log_config.json', settings)
    prune(settings)
    return settings
