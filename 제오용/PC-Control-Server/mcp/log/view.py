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

def read(path, default=None):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))

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

def run(limit=100, mission_id=None, type='all'):
    prune(log_config())
    entries = [read(path) for path in config.LOG_DIR.glob('*.json')]
    entries = [entry for entry in entries if (not mission_id or entry['mission_id'] == mission_id) and (type == 'all' or entry['type'] == type)]
    entries.sort(key=lambda entry: entry['timestamp'], reverse=True)
    return dict(count=len(entries[:limit]), logs=entries[:limit])
