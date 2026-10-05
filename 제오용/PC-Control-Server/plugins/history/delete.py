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

def mission_path(mission_id):
    if not isinstance(mission_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", mission_id) or mission_id == 'current':
        raise ValueError("유효하지 않은 작업 ID입니다.")
    return config.HISTORY_DIR / (mission_id + '.json')

def mission(mission_id):
    data = read(mission_path(mission_id))
    if data is None:
        raise FileNotFoundError("작업을 찾을 수 없습니다: " + mission_id)
    data.setdefault('results', {})
    return data

def current_id():
    return (read(config.HISTORY_DIR / 'current.json', {}) or {}).get('mission_id')

def run(mission_id):
    mission(mission_id)
    if current_id() == mission_id:
        (config.HISTORY_DIR / 'current.json').unlink(missing_ok=True)
    mission_path(mission_id).unlink()
    return dict(mission_id=mission_id, deleted=True)
