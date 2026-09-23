"""Explicit recordings and literal replay, never auto-retry."""
import threading
import time
from core import runtime as rt

recording = None
listeners = []
replaying = False
_guard = threading.RLock()


def append_event(event):
    with _guard:
        if recording is None or replaying:
            return
        if rt.stop_event.is_set():
            return
        event = {'at': time.monotonic()-recording['_started'], **event}
        recording['events'].append(event)


def automation(group, feature, arguments):
    if recording and recording['source'] in ('automation', 'both') and group in ('mouse','keyboard','input','window'):
        append_event({'kind': 'api', 'group': group, 'feature': feature, 'arguments': arguments})


def finish():
    global recording
    with _guard:
        if recording is None:
            rt.fail('기록 중인 매크로가 없습니다.', 409)
        for listener in listeners:
            listener.stop()
        listeners.clear()
        item = recording
        recording = None
        item.pop('_started', None)
        item['state'] = 'saved'
        rt.save('macro', item, item['mission_id'])
        return {'id': item['id'], 'events': len(item['events']), 'state': item['state']}


def record(name, source):
    global recording
    rt.check_stop()
    if source not in ('user','automation','both'):
        rt.fail('source는 user/automation/both입니다.')
    with _guard:
        if recording or replaying:
            rt.fail('매크로가 이미 기록/재생 중입니다.', 409)
        item = {'id': rt.uid(), 'name': name, 'source': source, 'mission_id': rt.current()['id'],
                'events': [], 'state': 'recording', 'created_at': rt.timestamp(), '_started': time.monotonic()}
        recording = item
        try:
            if source in ('user','both'):
                from pynput import keyboard, mouse
                def key_event(key, pressed, injected=False):
                    if injected or key is None:
                        return
                    vk = getattr(key, 'vk', None) or getattr(getattr(key, 'value', None), 'vk', None)
                    if vk is not None:
                        append_event({'kind':'key', 'vk':vk, 'pressed':pressed})
                def movement(x,y,injected=False):
                    if not injected:
                        append_event({'kind':'move','x':x,'y':y})
                def click(x,y,button,pressed,injected=False):
                    if not injected:
                        append_event({'kind':'button','x':x,'y':y,'button':button.name,'pressed':pressed})
                def scroll(x,y,dx,dy,injected=False):
                    if not injected:
                        append_event({'kind':'scroll','x':x,'y':y,'dx':dx,'dy':dy})
                listeners.extend([keyboard.Listener(on_press=lambda k, injected=False:key_event(k,True,injected),
                    on_release=lambda k, injected=False:key_event(k,False,injected)),
                    mouse.Listener(on_move=movement, on_click=click, on_scroll=scroll)])
                for listener in listeners:
                    listener.start()
                    listener.wait()
        except BaseException:
            for listener in listeners:
                listener.stop()
            listeners.clear()
            recording = None
            raise
        return {'id': item['id'], 'state':'recording'}


def replay(macro_id):
    global replaying
    item = rt.get('macro', macro_id)
    with _guard:
        if recording or replaying:
            rt.fail('기록/재생 중에는 재생할 수 없습니다.',409)
        replaying = True
    completed = 0
    down = set()
    try:
        from core import desktop
        import ctypes
        from pynput.mouse import Controller
        mouse = Controller()
        with rt.input_lock:
            start = time.monotonic()
            for event in item['events']:
                rt.sleep(max(0, event['at']-(time.monotonic()-start)))
                kind = event['kind']
                if kind == 'api':
                    from core.dispatch import execute
                    execute(event['group'], event['feature'], event['arguments'], record=False)
                elif kind == 'move':
                    desktop.move(event['x'],event['y'],0)
                elif kind == 'key':
                    vk = event['vk']
                    if event['pressed']:
                        down.add(vk)
                    ctypes.windll.user32.keybd_event(vk, 0, 0 if event['pressed'] else 2, 0)
                    if not event['pressed']:
                        down.discard(vk)
                elif kind == 'button':
                    desktop.move(event['x'],event['y'],0)
                    button = event['button']
                    if event['pressed']:
                        rt.held_buttons.add(button)
                        desktop.gui().mouseDown(button=button)
                    else:
                        desktop.gui().mouseUp(button=button)
                        rt.held_buttons.discard(button)
                elif kind == 'scroll':
                    desktop.move(event['x'],event['y'],0)
                    mouse.scroll(event['dx'],event['dy'])
                completed += 1
        return {'macro_id':macro_id,'executed':completed,'total':len(item['events'])}
    except Exception:
        rt.log_work({'action':'macro/replay','macro_id':macro_id,'success':False,'executed':completed})
        raise
    finally:
        import ctypes
        for vk in down:
            ctypes.windll.user32.keybd_event(vk,0,2,0)
        from core.desktop import release_all
        release_all()
        replaying = False


def run(action, **kw):
    if action == 'record':
        return record(kw['name'], kw['source'])
    if action == 'stop':
        return finish()
    if action == 'list':
        result = [{k:v for k,v in m.items() if k != 'events'} | {'event_count':len(m['events'])} for m in rt.items('macro')]
        if recording and recording['mission_id'] == rt.current()['id']:
            result.append({'id':recording['id'],'state':'recording','event_count':len(recording['events'])})
        return result
    if action == 'replay':
        return replay(kw['macro_id'])
    from core.imaging import save_capture, compare
    opts = rt.options(kw['verify'], {'target','expect','tolerance'})
    expect = opts.get('expect','changed')
    if expect not in ('changed','unchanged'):
        rt.fail('expect는 changed 또는 unchanged입니다.')
    target = opts.get('target', {})
    before = save_capture(target)
    result = replay(kw['macro_id'])
    after = save_capture(target)
    checked = compare(before['id'],after['id'],opts.get('tolerance',0))
    checked['passed'] = checked['changed'] == (expect == 'changed')
    return {**result,'verification':checked}
