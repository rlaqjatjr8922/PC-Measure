import config
import ctypes
import math
from fastapi import HTTPException
try:
    ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
except (AttributeError, OSError):
    pass

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

def run(**kw):
    import win32gui as wg
    import win32con as wc
    import win32process as wp

    def info(hwnd):
        left, top, right, bottom = wg.GetWindowRect(hwnd)
        return {'hwnd': hwnd, 'title': wg.GetWindowText(hwnd), 'pid': wp.GetWindowThreadProcessId(hwnd)[1], 'x': left, 'y': top, 'width': right - left, 'height': bottom - top, 'visible': bool(wg.IsWindowVisible(hwnd)), 'minimized': bool(wg.IsIconic(hwnd)), 'maximized': wg.GetWindowPlacement(hwnd)[1] == wc.SW_SHOWMAXIMIZED, 'focused': wg.GetForegroundWindow() == hwnd}
    hwnd = _number(kw['hwnd'], 1, integer=True)
    if not wg.IsWindow(hwnd):
        _fail('창을 찾을 수 없습니다.', 404)
    if 'position' == 'position' and kw['mode'] == 'get':
        return info(hwnd)
    with config.input_lock:
        _check_stop()
        wg.MoveWindow(hwnd, _number(kw['x'], integer=True), _number(kw['y'], integer=True), _number(kw['width'], 1, integer=True), _number(kw['height'], 1, integer=True), True)
        return info(hwnd)
