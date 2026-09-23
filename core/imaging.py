import hashlib
from io import BytesIO
import time
from PIL import Image, ImageChops, ImageStat
from core import runtime as rt


def capture(target):
    import mss
    import mss.tools
    target = rt.options(target, {'monitor', 'hwnd', 'region'})
    if sum(k in target for k in ('monitor', 'hwnd', 'region')) > 1:
        rt.fail('화면 대상은 하나만 지정하세요.')
    with mss.mss() as sct:
        if 'hwnd' in target:
            import win32gui
            hwnd = rt.number(target['hwnd'], 1, integer=True)
            if not win32gui.IsWindow(hwnd):
                rt.fail('창을 찾을 수 없습니다.', 404)
            x,y,r,b = win32gui.GetWindowRect(hwnd)
            area = {'left': x, 'top': y, 'width': r-x, 'height': b-y}
        elif 'region' in target:
            region = target['region']
            if not isinstance(region, dict) or set(region) != {'x','y','width','height'}:
                rt.fail('region에는 x,y,width,height가 필요합니다.')
            area = {'left': rt.number(region['x'], integer=True), 'top': rt.number(region['y'], integer=True),
                    'width': rt.number(region['width'], 1, integer=True), 'height': rt.number(region['height'], 1, integer=True)}
        else:
            import config
            index = rt.number(target.get('monitor', config.screen['selected_monitor']), 0, len(sct.monitors)-1, True)
            area = dict(sct.monitors[index])
        if area['width'] <= 0 or area['height'] <= 0:
            rt.fail('캡처 영역이 비어 있습니다.')
        shot = sct.grab(area)
        return mss.tools.to_png(shot.rgb, shot.size), area


def save_capture(target):
    rt.current()
    raw, area = capture(target)
    ident = rt.uid()
    folder = rt.mission_dir() / 'screenshots'
    folder.mkdir(exist_ok=True)
    (folder / (ident+'.png')).write_bytes(raw)
    record = {'id': ident, 'area': area, 'target': target, 'created_at': rt.timestamp(),
              'hash': image_hash(raw), 'image_url': '/screen/screenshot?mode=read&screenshot_id='+ident}
    rt.save('screenshot', record, rt.current()['id'])
    return record


def raw_image(ident):
    rt.get('screenshot', ident)
    return (rt.mission_dir() / 'screenshots' / (ident+'.png')).read_bytes()


def image_hash(raw):
    with Image.open(BytesIO(raw)) as image:
        image = image.convert('RGB')
        return hashlib.sha256(str(image.size).encode()+image.tobytes()).hexdigest()


def screenshot(mode, **kw):
    if mode == 'read':
        return raw_image(kw['screenshot_id'])
    if mode == 'save':
        return save_capture(kw['target'])
    return capture(kw['target'])[0]


def marker(mode, **kw):
    if mode == 'list':
        rt.get('screenshot', kw['screenshot_id'])
        return [m for m in rt.items('marker') if m['screenshot_id'] == kw['screenshot_id']]
    with rt.lock:
        if mode == 'add':
            s = rt.get('screenshot', kw['screenshot_id'])
            item = {'id': rt.uid(), 'screenshot_id': s['id']}
            item['marker_id'] = item['id']
        else:
            item = rt.get('marker', kw['marker_id'])
            s = rt.get('screenshot', item['screenshot_id'])
        if mode == 'delete':
            rt.delete('marker', item['id'])
            return {'deleted': True}
        if mode in ('add', 'update'):
            data = rt.options(kw['data'], {'x', 'y', 'annotation'})
            for axis, maximum in [('x', s['area']['width']), ('y', s['area']['height'])]:
                item[axis] = rt.number(data.get(axis, item.get(axis)), 0, maximum-1, True)
            item['annotation'] = str(data.get('annotation', item.get('annotation','')))
            return rt.save('marker', item, rt.current()['id'])
        return item


def compare(before, after, tolerance):
    tolerance = rt.number(tolerance, 0, 255, True)
    a, b = rt.get('screenshot', before), rt.get('screenshot', after)
    if a['area'] != b['area']:
        rt.fail('동일한 캡처 영역만 비교할 수 있습니다.')
    with Image.open(BytesIO(raw_image(before))) as ia, Image.open(BytesIO(raw_image(after))) as ib:
        delta = ImageChops.difference(ia.convert('RGB'), ib.convert('RGB'))
        channels = delta.split()
        maximum = ImageChops.lighter(ImageChops.lighter(channels[0], channels[1]), channels[2])
        histogram = maximum.histogram()
        changed = sum(histogram[tolerance+1:])
        return {'changed': changed > 0, 'changed_pixels': changed,
                'changed_ratio': changed/(ia.width*ia.height), 'mean_difference': sum(ImageStat.Stat(delta).mean)/3}


def verify(action, **kw):
    if action == 'hash':
        return save_capture(kw['target'])
    if action == 'wait_stable':
        opts = rt.options(kw['options'], {'interval', 'stable_for', 'max_wait', 'tolerance'})
        interval = rt.number(opts.get('interval', .2), .02, 60)
        stable_for = rt.number(opts.get('stable_for', 1), .02, 3600)
        max_wait = rt.number(opts.get('max_wait', 10), .02, 3600)
        tolerance = rt.number(opts.get('tolerance', 0), 0, 255, True)
        start = time.monotonic()
        anchor = save_capture(kw['target'])
        stable_since = time.monotonic()
        last = anchor
        while time.monotonic()-start < max_wait:
            rt.sleep(max(0, min(interval, max_wait-(time.monotonic()-start))))
            last = save_capture(kw['target'])
            if compare(anchor['id'], last['id'], tolerance)['changed']:
                anchor = last
                stable_since = time.monotonic()
            if time.monotonic()-stable_since >= stable_for:
                return {'stable': True, 'screenshot_id': last['id'], 'elapsed': time.monotonic()-start}
        return {'stable': False, 'screenshot_id': last['id'], 'elapsed': time.monotonic()-start}
    rt.get('screenshot', kw['before_id'])
    if kw['mode'] == 'current':
        after = save_capture(kw['target'])['id']
    else:
        after = kw['after_id']
    result = compare(kw['before_id'], after, kw['tolerance'])
    result.update(before_id=kw['before_id'], after_id=after)
    if action.startswith('assert_'):
        result['passed'] = result['changed'] if action == 'assert_changed' else not result['changed']
    return result
