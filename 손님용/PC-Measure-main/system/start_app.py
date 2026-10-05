"""Launch an executable without applying file-mutation hardlink restrictions."""
import os
from pathlib import Path
import subprocess
import ctypes
from ctypes import wintypes
import config
from fastapi import HTTPException

def _within(path, root):
    return path == root or root in path.parents

def _system_directory():
    buf = ctypes.create_unicode_buffer(32768)
    fn = ctypes.windll.kernel32.GetSystemDirectoryW
    fn.argtypes = [wintypes.LPWSTR, wintypes.UINT]
    fn.restype = wintypes.UINT
    size = fn(buf, len(buf))
    if not size or size >= len(buf):
        raise HTTPException(500, 'Windows 시스템 경로를 확인할 수 없습니다.')
    return Path(buf.value)

def run(executable, args=None):
    if config.stop_event.is_set() or config.KILL_SWITCH:
        raise HTTPException(409, 'KILL_SWITCH: 작업이 중지되었습니다.')
    if not isinstance(executable, str) or not executable.strip():
        raise HTTPException(400, '실행 파일 이름 또는 절대 경로가 필요합니다.')
    args = [] if args is None else args
    if not isinstance(args, list) or any(not isinstance(a, str) or '\0' in a for a in args):
        raise HTTPException(400, 'args는 문자열 배열이어야 합니다.')
    raw = executable.strip()
    if '\0' in raw or raw.startswith(chr(92) * 2) or ':' in raw[2:]:
        raise HTTPException(403, '장치, 네트워크, 대체 데이터 스트림 경로는 허용하지 않습니다.')
    p = Path(raw)
    if not p.is_absolute():
        if p.name != raw or '/' in raw or '\\' in raw or p.drive:
            raise HTTPException(400, '상대 경로 대신 실행 파일 이름 또는 절대 경로를 지정하세요.')
        # Never search the current directory or an attacker-controlled PATH.
        p = _system_directory() / (raw if p.suffix else raw + '.exe')
    p = p.resolve()
    if any(_within(p, root.resolve()) for root in (config.PRIVATE, config.BASE_DIR)):
        raise HTTPException(403, '서버 내부 파일은 실행할 수 없습니다.')
    if p.suffix.lower() != '.exe':
        raise HTTPException(400, '.exe 실행 파일을 지정하세요.')
    if not p.is_file():
        raise HTTPException(404, '실행 파일을 찾을 수 없습니다.')
    proc = subprocess.Popen([str(p), *args], shell=False, close_fds=True)
    return {'pid': proc.pid, 'started': True, 'executable': str(p)}
