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

def save(data):
    data['updated_at'] = now()
    write(mission_path(data['mission_id']), data)
    return data

def run(mission_id, title=None, goal=None, plan=None):
    data = mission(mission_id)
    for key, value in dict(title=title, goal=goal).items():
        if value is not None:
            data[key] = value
    if plan is not None and plan != data['plan']:
        # Keep progress only where the step itself has not changed.
        retained = {str(i) for i, step in enumerate(plan) if i < len(data['plan']) and step == data['plan'][i]}
        data['results'] = {k: v for k, v in data['results'].items() if k in retained}
        data['notes']['steps'] = {k: v for k, v in data['notes']['steps'].items() if k in retained}
        data['plan'] = plan
        data['current_step'] = min(data['current_step'], len(plan) - 1)
        data['status'] = 'completed' if len(data['results']) == len(plan) else 'working'
    return save(data)
