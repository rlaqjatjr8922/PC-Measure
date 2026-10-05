import config
from fastapi import HTTPException

def _check_stop():
    if config.stop_event.is_set() or config.KILL_SWITCH:
        _fail('KILL_SWITCH: 작업이 중지되었습니다. 서버를 재시작하세요.', 409)

def _fail(message, status=400):
    raise HTTPException(status, message)

def run(**kw):
    import win32clipboard as cb
    import win32con
    if kw['mode'] == 'write':
        _check_stop()
    cb.OpenClipboard()
    try:
        if kw['mode'] == 'read':
            return {'text': cb.GetClipboardData(win32con.CF_UNICODETEXT) if cb.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT) else ''}
        cb.EmptyClipboard()
        cb.SetClipboardText(str(kw['text']), win32con.CF_UNICODETEXT)
        return {'written': True}
    finally:
        cb.CloseClipboard()
