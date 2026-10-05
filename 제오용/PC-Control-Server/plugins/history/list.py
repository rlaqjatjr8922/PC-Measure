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

def run(query='all', status='all'):
    rows = []
    for path in config.HISTORY_DIR.glob('*.json'):
        if path.name == 'current.json':
            continue
        data = read(path)
        if query not in ('all', '') and query.casefold() not in data['title'].casefold():
            continue
        if status != 'all' and status != data['status']:
            continue
        rows.append({key: data.get(key) for key in ('mission_id', 'title', 'status', 'current_step', 'created_at', 'updated_at')})
    rows.sort(key=lambda row: row['updated_at'] or '', reverse=True)
    return dict(count=len(rows), missions=rows)
