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

def _mouse(action, **kw):
    g = _gui()
    if action == 'position':
        x, y = g.position()
        return {'x': x, 'y': y}
    with config.input_lock:
        _check_stop()
        opts = _options(kw.get('options', {}), {'duration', 'interval', 'button', 'clicks'})
        duration = _number(opts.get('duration', 0.0), 0, 120)
        interval = _number(opts.get('interval', 0.1), 0, 10)
        button = opts.get('button', 'left')
        if button not in ('left', 'right', 'middle'):
            _fail('잘못된 마우스 버튼입니다.')
        if action in ('hover', 'move'):
            return _move(kw['x'], kw['y'], duration)
        if action == 'scroll':
            amount = _number(kw['amount'], -10000, 10000, True)
            for _ in range(abs(amount)):
                _check_stop()
                g.scroll(1 if amount > 0 else -1)
            return {'amount': amount}
        if action == 'drag':
            _move(kw['start_x'], kw['start_y'], 0)
            config.held_buttons.add(button)
            try:
                _check_stop()
                g.mouseDown(button=button)
                return _move(kw['end_x'], kw['end_y'], duration)
            finally:
                g._pyautogui_win._mouseUp(*g.position(), button)
                config.held_buttons.discard(button)
        pos = _move(kw['x'], kw['y'], 0)
        if action == 'right_click':
            button = 'right'
        count = 2 if action == 'double_click' else _number(opts.get('clicks', 1), 1, 100, True)
        for i in range(count):
            _check_stop()
            config.held_buttons.add(button)
            try:
                g.mouseDown(button=button)
                _check_stop()
            finally:
                g._pyautogui_win._mouseUp(*g.position(), button)
                config.held_buttons.discard(button)
            if i + 1 < count:
                _sleep(interval)
        return {**pos, 'button': button, 'clicks': count}

def _move(x, y, duration):
    x, y = (_number(x, integer=True), _number(y, integer=True))
    duration = _number(duration, 0, 120)
    g = _gui()
    sx, sy = g.position()
    steps = max(1, math.ceil(duration / 0.02))
    for i in range(1, steps + 1):
        _check_stop()
        from windows_input import move_cursor
        move_cursor(round(sx + (x - sx) * i / steps), round(sy + (y - sy) * i / steps))
        if duration:
            _sleep(duration / steps)
    return {'x': x, 'y': y}

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

def _options(value, allowed):
    if not isinstance(value, dict) or set(value) - set(allowed):
        _fail('options 값 또는 항목이 올바르지 않습니다.')
    return value

def _sleep(seconds):
    seconds = _number(seconds, 0, 3600)
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        _check_stop()
        config.stop_event.wait(max(0, min(0.02, end - time.monotonic())))
    _check_stop()

def run(mode, **kwargs):
    if mode == 'position':
        return _mouse(mode)
    if mode == 'scroll':
        return _mouse(mode, **kwargs)
    options = {k: kwargs.pop(k) for k in ('button', 'clicks', 'interval', 'duration') if k in kwargs}
    if mode == 'click':
        kwargs.update(_mouse('position'))
    if mode == 'drag':
        start = _mouse('position')
        kwargs = {'start_x': start['x'], 'start_y': start['y'], 'end_x': kwargs['x'], 'end_y': kwargs['y']}
    return _mouse(mode, options=options, **kwargs)
