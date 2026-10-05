import json
from pathlib import Path
import config
from .parser import valid_url

def path(): return config.DATA_DIR/'remote'/'endpoint_cache.json'
def load(code,channel):
    try:
        data=json.loads(path().read_text(encoding='utf-8'))
        if data['pc_code']==code and data['channel_id']==channel and valid_url(data['base_url']): return data
    except (OSError,ValueError,KeyError,TypeError): pass
    return None

def save(data):
    target=path(); target.parent.mkdir(parents=True,exist_ok=True)
    temp=target.with_suffix('.tmp'); temp.write_text(json.dumps(data),encoding='utf-8'); temp.replace(target)
