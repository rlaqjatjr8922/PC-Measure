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

def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)

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

def run(mission_id):
    data = mission(mission_id)
    write(config.HISTORY_DIR / 'current.json', {'mission_id': mission_id})
    return data
