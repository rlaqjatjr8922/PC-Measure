"""Small Windows operations. All timing is interruptible."""
import ctypes
import math
import time
from core import runtime as rt

# Match screenshot physical pixels even when displays have different DPI scales.
try:
    ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
except (AttributeError, OSError):
    pass


def gui():
    import pyautogui
    pyautogui.PAUSE = 0
    return pyautogui


def release_all():
    g = gui()
    # Releases must still work with the emergency stop and PyAutoGUI fail-safe active.
    for key in tuple(rt.held_keys):
        try:
            g._pyautogui_win._keyUp(key)
        finally:
            rt.held_keys.discard(key)
    for button in tuple(rt.held_buttons):
        try:
            x, y = g.position()
            g._pyautogui_win._mouseUp(x, y, button)
        finally:
            rt.held_buttons.discard(button)


def move(x, y, duration):
    x, y = rt.number(x, integer=True), rt.number(y, integer=True)
    duration = rt.number(duration, 0, 120)
    g = gui()
    sx, sy = g.position()
    steps = max(1, math.ceil(duration / .02))
    for i in range(1, steps + 1):
        rt.check_stop()
        # Native SetCursorPos supports negative coordinates on additional monitors.
        if not ctypes.windll.user32.SetCursorPos(round(sx+(x-sx)*i/steps), round(sy+(y-sy)*i/steps)):
            raise ctypes.WinError()
        if duration:
            rt.sleep(duration / steps)
    return {'x': x, 'y': y}


def mouse(action, **kw):
    g = gui()
    if action == 'position':
        x,y = g.position()
        return {'x': x, 'y': y}
    with rt.input_lock:
        rt.check_stop()
        opts = rt.options(kw.get('options', {}), {'duration', 'interval', 'button', 'clicks'})
        duration = rt.number(opts.get('duration', .0), 0, 120)
        interval = rt.number(opts.get('interval', .1), 0, 10)
        button = opts.get('button', 'left')
        if button not in ('left', 'right', 'middle'):
            rt.fail('잘못된 마우스 버튼입니다.')
        if action in ('hover', 'move'):
            return move(kw['x'], kw['y'], duration)
        if action == 'scroll':
            amount = rt.number(kw['amount'], -10000, 10000, True)
            for _ in range(abs(amount)):
                rt.check_stop()
                g.scroll(1 if amount > 0 else -1)
            return {'amount': amount}
        if action == 'drag':
            move(kw['start_x'], kw['start_y'], 0)
            rt.held_buttons.add(button)
            try:
                rt.check_stop()
                g.mouseDown(button=button)
                return move(kw['end_x'], kw['end_y'], duration)
            finally:
                g._pyautogui_win._mouseUp(*g.position(), button)
                rt.held_buttons.discard(button)
        pos = move(kw['x'], kw['y'], 0)
        if action == 'right_click':
            button = 'right'
        count = 2 if action == 'double_click' else rt.number(opts.get('clicks', 1), 1, 100, True)
        for i in range(count):
            rt.check_stop()
            rt.held_buttons.add(button)
            try:
                g.mouseDown(button=button)
                rt.check_stop()
            finally:
                g._pyautogui_win._mouseUp(*g.position(), button)
                rt.held_buttons.discard(button)
            if i + 1 < count:
                rt.sleep(interval)
        return {**pos, 'button': button, 'clicks': count}


def unicode_char(char):
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
        code = int.from_bytes(data[i:i+2], 'little')
        for flags in (4, 6):
            item = INPUT()
            item.type = 1
            item.u.ki = KEYBDINPUT(0, code, flags, 0, 0)
            events.append(item)
    array = (INPUT * len(events))(*events)
    if ctypes.windll.user32.SendInput(len(events), array, ctypes.sizeof(INPUT)) != len(events):
        rt.fail('Windows가 Unicode 입력을 허용하지 않았습니다.', 500)


def keyboard(action, **kw):
    g = gui()
    with rt.input_lock:
        if action != 'release':
            rt.check_stop()
        if action == 'type':
            interval = rt.number(kw.get('interval', 0), 0, 10)
            text = kw['text']
            if not isinstance(text, str):
                rt.fail('text는 문자열이어야 합니다.')
            for char in text:
                rt.check_stop()
                if char in ('\n', '\t'):
                    g.press('enter' if char == '\n' else 'tab')
                elif char != '\r':
                    unicode_char(char)
                if interval:
                    rt.sleep(interval)
            return {'characters': len(text)}
        keys = kw.get('keys', [kw.get('key')])
        if isinstance(keys, str):
            keys = keys.split(',')
        if not isinstance(keys, list) or not keys:
            rt.fail('키 목록이 필요합니다.')
        keys = [str(k).strip().lower() for k in keys]
        if any(k not in g.KEYBOARD_KEYS for k in keys):
            rt.fail('지원하지 않는 키입니다.')
        if action == 'hold':
            rt.held_keys.add(keys[0])
            try:
                rt.check_stop()
                g.keyDown(keys[0])
                rt.check_stop()
            except BaseException:
                release_all()
                raise
        elif action == 'release':
            g._pyautogui_win._keyUp(keys[0])
            rt.held_keys.discard(keys[0])
        elif action == 'hotkey':
            try:
                for key in keys:
                    rt.check_stop()
                    rt.held_keys.add(key)
                    g.keyDown(key)
            finally:
                for key in reversed(keys):
                    g._pyautogui_win._keyUp(key)
                    rt.held_keys.discard(key)
        else:
            rt.held_keys.add(keys[0])
            try:
                g.keyDown(keys[0])
                rt.check_stop()
            finally:
                g._pyautogui_win._keyUp(keys[0])
                rt.held_keys.discard(keys[0])
        return {'keys': keys}


def window(action, **kw):
    import win32gui as wg
    import win32con as wc
    import win32process as wp
    def info(hwnd):
        left, top, right, bottom = wg.GetWindowRect(hwnd)
        return {'hwnd': hwnd, 'title': wg.GetWindowText(hwnd), 'pid': wp.GetWindowThreadProcessId(hwnd)[1],
                'x': left, 'y': top, 'width': right-left, 'height': bottom-top,
                'visible': bool(wg.IsWindowVisible(hwnd)), 'minimized': bool(wg.IsIconic(hwnd)),
                'maximized': wg.GetWindowPlacement(hwnd)[1] == wc.SW_SHOWMAXIMIZED,
                'focused': wg.GetForegroundWindow() == hwnd}
    if action in ('list', 'find'):
        found = []
        def callback(hwnd, _):
            if wg.IsWindowVisible(hwnd) and wg.GetWindowText(hwnd):
                try:
                    found.append(info(hwnd))
                except Exception:
                    pass  # Window may close between enumeration and lookup.
        wg.EnumWindows(callback, None)
        if action == 'find':
            title = str(kw['title']).casefold()
            found = [v for v in found if title in v['title'].casefold()]
        return found
    hwnd = rt.number(kw['hwnd'], 1, integer=True)
    if not wg.IsWindow(hwnd):
        if action == 'state':
            return {'hwnd': hwnd, 'exists': False}
        rt.fail('창을 찾을 수 없습니다.', 404)
    if action == 'state':
        return {'exists': True, **info(hwnd)}
    if action == 'position' and kw['mode'] == 'get':
        return info(hwnd)
    with rt.input_lock:
        rt.check_stop()
        if action == 'focus':
            if wg.IsIconic(hwnd):
                wg.ShowWindow(hwnd, wc.SW_RESTORE)
            wg.SetForegroundWindow(hwnd)
        elif action in ('maximize', 'minimize'):
            wg.ShowWindow(hwnd, wc.SW_MAXIMIZE if action == 'maximize' else wc.SW_MINIMIZE)
        elif action == 'close':
            wg.PostMessage(hwnd, wc.WM_CLOSE, 0, 0)
            return {'hwnd': hwnd, 'close_requested': True}
        elif action == 'position':
            wg.MoveWindow(hwnd, rt.number(kw['x'], integer=True), rt.number(kw['y'], integer=True),
                          rt.number(kw['width'], 1, integer=True), rt.number(kw['height'], 1, integer=True), True)
        return info(hwnd)
