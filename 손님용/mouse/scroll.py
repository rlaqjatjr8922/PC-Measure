import config
import ctypes
import math
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

def run(**kw):
    g = _gui()
    with config.input_lock:
        _check_stop()
        opts = _options(kw.get('options', {}), {'duration', 'interval', 'button', 'clicks'})
        duration = _number(opts.get('duration', 0.0), 0, 120)
        interval = _number(opts.get('interval', 0.1), 0, 10)
        button = opts.get('button', 'left')
        if button not in ('left', 'right', 'middle'):
            _fail('잘못된 마우스 버튼입니다.')
        amount = _number(kw['amount'], -10000, 10000, True)
        for _ in range(abs(amount)):
            _check_stop()
            g.scroll(1 if amount > 0 else -1)
        return {'amount': amount}
