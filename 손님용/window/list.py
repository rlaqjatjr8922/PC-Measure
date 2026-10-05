import ctypes
try:
    ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
except (AttributeError, OSError):
    pass

def run(**kw):
    import win32gui as wg
    import win32con as wc
    import win32process as wp

    def info(hwnd):
        left, top, right, bottom = wg.GetWindowRect(hwnd)
        return {'hwnd': hwnd, 'title': wg.GetWindowText(hwnd), 'pid': wp.GetWindowThreadProcessId(hwnd)[1], 'x': left, 'y': top, 'width': right - left, 'height': bottom - top, 'visible': bool(wg.IsWindowVisible(hwnd)), 'minimized': bool(wg.IsIconic(hwnd)), 'maximized': wg.GetWindowPlacement(hwnd)[1] == wc.SW_SHOWMAXIMIZED, 'focused': wg.GetForegroundWindow() == hwnd}
    found = []

    def callback(hwnd, _):
        if wg.IsWindowVisible(hwnd) and wg.GetWindowText(hwnd):
            try:
                found.append(info(hwnd))
            except Exception:
                pass
    wg.EnumWindows(callback, None)
    return found
