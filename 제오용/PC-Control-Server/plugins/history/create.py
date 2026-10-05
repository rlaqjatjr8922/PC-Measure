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

def save(data):
    data['updated_at'] = now()
    write(mission_path(data['mission_id']), data)
    return data

def run(title, goal, plan):
    data = dict(mission_id=uuid.uuid4().hex[:12], title=title, goal=goal, plan=plan,
                status='working', current_step=0, notes={'mission': [], 'steps': {}},
                results={}, rejects=[], created_at=now())
    return save(data)
