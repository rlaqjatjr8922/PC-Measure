"""Typed Windows input APIs shared by the HTTP worker threads."""
import ctypes
from ctypes import wintypes as w
from fastapi import HTTPException

class MOUSEINPUT(ctypes.Structure):
    _fields_ = [('dx', w.LONG), ('dy', w.LONG), ('mouseData', w.DWORD),
                ('dwFlags', w.DWORD), ('time', w.DWORD), ('dwExtraInfo', ctypes.c_size_t)]
class KEYBDINPUT(ctypes.Structure):
    _fields_ = [('wVk', w.WORD), ('wScan', w.WORD), ('dwFlags', w.DWORD),
                ('time', w.DWORD), ('dwExtraInfo', ctypes.c_size_t)]
class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [('uMsg', w.DWORD), ('wParamL', w.WORD), ('wParamH', w.WORD)]
class INPUTUNION(ctypes.Union):
    _fields_ = [('mi', MOUSEINPUT), ('ki', KEYBDINPUT), ('hi', HARDWAREINPUT)]
class INPUT(ctypes.Structure):
    _anonymous_ = ('value',)
    _fields_ = [('type', w.DWORD), ('value', INPUTUNION)]

user32 = ctypes.WinDLL('user32', use_last_error=True)
user32.SendInput.argtypes = [w.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
user32.SendInput.restype = w.UINT
user32.GetSystemMetrics.argtypes = [ctypes.c_int]
user32.GetSystemMetrics.restype = ctypes.c_int

def move_cursor(x, y):
    left, top, width, height = [user32.GetSystemMetrics(i) for i in (76, 77, 78, 79)]
    if width <= 0 or height <= 0:
        raise HTTPException(409, 'DESKTOP_UNAVAILABLE: 로그인된 데스크톱이 필요합니다.')
    if not (left <= x < left + width and top <= y < top + height):
        raise HTTPException(400, '마우스 좌표가 전체 모니터 영역 밖입니다.')
    event = INPUT(type=0, mi=MOUSEINPUT(
        dx=min(65535, ((x-left)*65536 + 32768)//width),
        dy=min(65535, ((y-top)*65536 + 32768)//height),
        dwFlags=0x0001 | 0x8000 | 0x4000))
    ctypes.set_last_error(0)
    if user32.SendInput(1, ctypes.byref(event), ctypes.sizeof(INPUT)) != 1:
        raise HTTPException(403, 'INPUT_BLOCKED: Windows가 입력을 허용하지 않습니다. 로그인 상태와 대상 앱의 실행 권한을 확인하세요.')

def focus_window(hwnd):
    import win32gui as wg
    import win32con as wc
    import win32process as wp
    import win32api
    if wg.GetForegroundWindow() == hwnd:
        return
    if wg.IsIconic(hwnd):
        wg.ShowWindow(hwnd, wc.SW_RESTORE)
    try:
        wg.SetForegroundWindow(hwnd)
    except Exception:
        pass
    if wg.GetForegroundWindow() == hwnd:
        return
    current = win32api.GetCurrentThreadId()
    attached = []
    try:
        foreground = wg.GetForegroundWindow()
        tids = {wp.GetWindowThreadProcessId(hwnd)[0]}
        if foreground:
            tids.add(wp.GetWindowThreadProcessId(foreground)[0])
        for tid in tids - {current}:
            if tid:
                wp.AttachThreadInput(current, tid, True)
                attached.append(tid)
        wg.BringWindowToTop(hwnd)
        wg.SetForegroundWindow(hwnd)
    except Exception:
        pass
    finally:
        for tid in reversed(attached):
            try:
                wp.AttachThreadInput(current, tid, False)
            except Exception:
                pass
    if wg.GetForegroundWindow() != hwnd:
        raise HTTPException(409, 'FOCUS_DENIED: Windows가 포커스 전환을 거부했습니다. 대상 창의 상태와 실행 권한을 확인하세요.')
