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

def _release_all():
    g = _gui()
    for key in tuple(config.held_keys):
        try:
            g._pyautogui_win._keyUp(key)
        finally:
            config.held_keys.discard(key)
    for button in tuple(config.held_buttons):
        try:
            x, y = g.position()
            g._pyautogui_win._mouseUp(x, y, button)
        finally:
            config.held_buttons.discard(button)

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
        config.held_keys.add(keys[0])
        try:
            _check_stop()
            g.keyDown(keys[0])
            _check_stop()
        except BaseException:
            _release_all()
            raise
        return {'keys': keys}
