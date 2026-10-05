import ctypes
try:
    ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
except (AttributeError, OSError):
    pass

def _gui():
    import pyautogui
    pyautogui.PAUSE = 0
    return pyautogui

def run(**kw):
    g = _gui()
    x, y = g.position()
    return {'x': x, 'y': y}
