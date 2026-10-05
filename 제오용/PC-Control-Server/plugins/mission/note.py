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

def current():
    mid = current_id()
    if not mid:
        raise ValueError("먼저 /history/select에서 작업을 선택하세요.")
    return mission(mid)

def save(data):
    data['updated_at'] = now()
    write(mission_path(data['mission_id']), data)
    return data

def run(text, scope='step'):
    data = current()
    note = dict(text=text, created_at=now())
    if scope == 'mission':
        data['notes']['mission'].append(note)
    else:
        data['notes']['steps'].setdefault(str(data['current_step']), []).append(note)
    return save(data)
