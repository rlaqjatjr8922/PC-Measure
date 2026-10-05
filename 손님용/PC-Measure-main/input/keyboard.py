import config
import ctypes
import math
import time
from fastapi import HTTPException
try:
    ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
except (AttributeError, OSError):
    pass

def _gui():
    import pyautogui
    pyautogui.PAUSE = 0
    return pyautogui

def _keyboard(action, **kw):
    g = _gui()
    with config.input_lock:
        if action != 'release':
            _check_stop()
        if action == 'type':
            interval = _number(kw.get('interval', 0), 0, 10)
            text = kw['text']
            if not isinstance(text, str):
                _fail('text는 문자열이어야 합니다.')
            for char in text:
                _check_stop()
                if char in ('\n', '\t'):
                    g.press('enter' if char == '\n' else 'tab')
                elif char != '\r':
                    _unicode_char(char)
                if interval:
                    _sleep(interval)
            return {'characters': len(text)}
        keys = kw.get('keys', [kw.get('key')])
        if isinstance(keys, str):
            keys = keys.split(',')
        if not isinstance(keys, list) or not keys:
            _fail('키 목록이 필요합니다.')
        keys = [str(k).strip().lower() for k in keys]
        if any((k not in g.KEYBOARD_KEYS for k in keys)):
            _fail('지원하지 않는 키입니다.')
        if action == 'hold':
            config.held_keys.add(keys[0])
            try:
                _check_stop()
                g.keyDown(keys[0])
                _check_stop()
            except BaseException:
                _release_all()
                raise
        elif action == 'release':
            g._pyautogui_win._keyUp(keys[0])
            config.held_keys.discard(keys[0])
        elif action == 'hotkey':
            try:
                for key in keys:
                    _check_stop()
                    config.held_keys.add(key)
                    g.keyDown(key)
            finally:
                for key in reversed(keys):
                    g._pyautogui_win._keyUp(key)
                    config.held_keys.discard(key)
        else:
            config.held_keys.add(keys[0])
            try:
                g.keyDown(keys[0])
                _check_stop()
            finally:
                g._pyautogui_win._keyUp(keys[0])
                config.held_keys.discard(keys[0])
        return {'keys': keys}

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

def _unicode_char(char):
    from ctypes import wintypes as w

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [('wVk', w.WORD), ('wScan', w.WORD), ('dwFlags', w.DWORD), ('time', w.DWORD), ('dwExtraInfo', ctypes.c_size_t)]

    class MOUSEINPUT(ctypes.Structure):
        _fields_ = [('dx', w.LONG), ('dy', w.LONG), ('mouseData', w.DWORD), ('dwFlags', w.DWORD), ('time', w.DWORD), ('dwExtraInfo', ctypes.c_size_t)]

    class HARDWAREINPUT(ctypes.Structure):
        _fields_ = [('uMsg', w.DWORD), ('wParamL', w.WORD), ('wParamH', w.WORD)]

    class UNION(ctypes.Union):
        _fields_ = [('ki', KEYBDINPUT), ('mi', MOUSEINPUT), ('hi', HARDWAREINPUT)]

    class INPUT(ctypes.Structure):
        _fields_ = [('type', w.DWORD), ('u', UNION)]
    data = char.encode('utf-16-le')
    events = []
    for i in range(0, len(data), 2):
        code = int.from_bytes(data[i:i + 2], 'little')
        for flags in (4, 6):
            item = INPUT()
            item.type = 1
            item.u.ki = KEYBDINPUT(0, code, flags, 0, 0)
            events.append(item)
    array = (INPUT * len(events))(*events)
    if ctypes.windll.user32.SendInput(len(events), array, ctypes.sizeof(INPUT)) != len(events):
        _fail('Windows가 Unicode 입력을 허용하지 않았습니다.', 500)

def _check_stop():
    if config.stop_event.is_set() or config.KILL_SWITCH:
        _fail('KILL_SWITCH: 작업이 중지되었습니다. 서버를 재시작하세요.', 409)

def _fail(message, status=400):
    raise HTTPException(status, message)

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

def _sleep(seconds):
    seconds = _number(seconds, 0, 3600)
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        _check_stop()
        config.stop_event.wait(max(0, min(0.02, end - time.monotonic())))
    _check_stop()

def run(mode, **kwargs):
    return _keyboard('press' if mode == 'key' else mode, **kwargs)
