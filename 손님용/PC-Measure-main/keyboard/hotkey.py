import config
import ctypes
from fastapi import HTTPException
try:
    ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
except (AttributeError, OSError):
    pass

def _gui():
    import pyautogui
    pyautogui.PAUSE = 0
    return pyautogui

def _check_stop():
    if config.stop_event.is_set() or config.KILL_SWITCH:
        _fail('KILL_SWITCH: 작업이 중지되었습니다. 서버를 재시작하세요.', 409)

def _fail(message, status=400):
    raise HTTPException(status, message)

def run(**kw):
    g = _gui()
    with config.input_lock:
        _check_stop()
        keys = kw.get('keys', [kw.get('key')])
        if isinstance(keys, str):
            keys = keys.split(',')
        if not isinstance(keys, list) or not keys:
            _fail('키 목록이 필요합니다.')
        keys = [str(k).strip().lower() for k in keys]
        if any((k not in g.KEYBOARD_KEYS for k in keys)):
            _fail('지원하지 않는 키입니다.')
        try:
            for key in keys:
                _check_stop()
                config.held_keys.add(key)
                g.keyDown(key)
        finally:
            for key in reversed(keys):
                g._pyautogui_win._keyUp(key)
                config.held_keys.discard(key)
        return {'keys': keys}
