import config
import hashlib
from io import BytesIO
from PIL import Image, ImageChops, ImageStat
import json
import sqlite3
import secrets
from contextlib import closing
from datetime import datetime, timezone
from fastapi import HTTPException

def _capture(target):
    import mss
    import mss.tools
    target = _options(target, {'monitor', 'hwnd', 'region'})
    if sum((k in target for k in ('monitor', 'hwnd', 'region'))) > 1:
        _fail('화면 대상은 하나만 지정하세요.')
    with mss.mss() as sct:
        if 'hwnd' in target:
            import win32gui
            hwnd = _number(target['hwnd'], 1, integer=True)
            if not win32gui.IsWindow(hwnd):
                _fail('창을 찾을 수 없습니다.', 404)
            x, y, r, b = win32gui.GetWindowRect(hwnd)
            area = {'left': x, 'top': y, 'width': r - x, 'height': b - y}
        elif 'region' in target:
            region = target['region']
            if not isinstance(region, dict) or set(region) != {'x', 'y', 'width', 'height'}:
                _fail('region에는 x,y,width,height가 필요합니다.')
            area = {'left': _number(region['x'], integer=True), 'top': _number(region['y'], integer=True), 'width': _number(region['width'], 1, integer=True), 'height': _number(region['height'], 1, integer=True)}
        else:
            import config
            index = _number(target.get('monitor', config.screen['selected_monitor']), 0, len(sct.monitors) - 1, True)
            area = dict(sct.monitors[index])
        if area['width'] <= 0 or area['height'] <= 0:
            _fail('캡처 영역이 비어 있습니다.')
        shot = sct.grab(area)
        return (mss.tools.to_png(shot.rgb, shot.size), area)

def _compare(before, after, tolerance):
    tolerance = _number(tolerance, 0, 255, True)
    a, b = (_get('screenshot', before), _get('screenshot', after))
    if a['area'] != b['area']:
        _fail('동일한 캡처 영역만 비교할 수 있습니다.')
    with Image.open(BytesIO(_raw_image(before))) as ia, Image.open(BytesIO(_raw_image(after))) as ib:
        delta = ImageChops.difference(ia.convert('RGB'), ib.convert('RGB'))
        channels = delta.split()
        maximum = ImageChops.lighter(ImageChops.lighter(channels[0], channels[1]), channels[2])
        histogram = maximum.histogram()
        changed = sum(histogram[tolerance + 1:])
        return {'changed': changed > 0, 'changed_pixels': changed, 'changed_ratio': changed / (ia.width * ia.height), 'mean_difference': sum(ImageStat.Stat(delta).mean) / 3}

def _image_hash(raw):
    with Image.open(BytesIO(raw)) as image:
        image = image.convert('RGB')
        return hashlib.sha256(str(image.size).encode() + image.tobytes()).hexdigest()

def _raw_image(ident):
    _get('screenshot', ident)
    return (config.DATA_DIR / 'screenshots' / (ident + '.png')).read_bytes()

def _save_capture(target):
    raw, area = _capture(target)
    ident = _uid()
    folder = config.DATA_DIR / 'screenshots'
    folder.mkdir(parents=True, exist_ok=True)
    (folder / (ident + '.png')).write_bytes(raw)
    record = {'id': ident, 'area': area, 'target': target, 'created_at': _timestamp(), 'hash': _image_hash(raw), 'image_url': '/screen/screenshot?mode=read&screenshot_id=' + ident}
    _save('screenshot', record)
    return record

def _fail(message, status=400):
    raise HTTPException(status, message)

def _get(kind, ident):
    _init()
    with closing(sqlite3.connect(config.DB)) as db:
        row = db.execute('SELECT value FROM objects WHERE kind=? AND id=?', (kind, str(ident))).fetchone()
    if not row:
        _fail('대상을 찾을 수 없습니다.', 404)
    return json.loads(row[0])

def _init():
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    config.PRIVATE.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(config.DB)) as db, db:
        db.execute('CREATE TABLE IF NOT EXISTS objects (kind TEXT, id TEXT, value TEXT, PRIMARY KEY(kind,id))')

def _number(value, minimum=None, maximum=None, integer=False):
    import math
    if isinstance(value, bool):
        _fail('숫자에 bool을 사용할 수 없습니다.')
    try:
        out = float(value)
    except (ValueError, TypeError):
        _fail('숫자 값이 필요합니다.')
    if not math.isfinite(out) or (integer and out != int(out)):
        _fail('유효한 숫자 값이 필요합니다.')
    if minimum is not None and out < minimum or (maximum is not None and out > maximum):
        _fail('숫자 값이 허용 범위를 벗어났습니다.')
    return int(out) if integer else out

def _options(value, allowed):
    if not isinstance(value, dict) or set(value) - set(allowed):
        _fail('options 값 또는 항목이 올바르지 않습니다.')
    return value

def _save(kind, item):
    _init()
    with config.lock, closing(sqlite3.connect(config.DB)) as db, db:
        db.execute('INSERT OR REPLACE INTO objects VALUES (?,?,?)', (kind, item['id'], json.dumps(item, ensure_ascii=False)))
    return item

def _timestamp():
    return datetime.now(timezone.utc).isoformat()

def _uid():
    return secrets.token_hex(16)

def run(**kw):
    _get('screenshot', kw['before_id'])
    if kw['mode'] == 'current':
        after = _save_capture(kw['target'])['id']
    else:
        after = kw['after_id']
    result = _compare(kw['before_id'], after, kw['tolerance'])
    result.update(before_id=kw['before_id'], after_id=after)
    result['passed'] = not result['changed']
    return result
