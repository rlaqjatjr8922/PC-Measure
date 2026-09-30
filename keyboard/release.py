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

def _fail(message, status=400):
    raise HTTPException(status, message)

def run(**kw):
    g = _gui()
    with config.input_lock:
        keys = kw.get('keys', [kw.get('key')])
        if isinstance(keys, str):
            keys = keys.split(',')
        if not isinstance(keys, list) or not keys:
            _fail('키 목록이 필요합니다.')
        keys = [str(k).strip().lower() for k in keys]
        if any((k not in g.KEYBOARD_KEYS for k in keys)):
            _fail('지원하지 않는 키입니다.')
        g._pyautogui_win._keyUp(keys[0])
        config.held_keys.discard(keys[0])
        return {'keys': keys}
