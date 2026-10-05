import config
import base64
import hashlib
import os
from pathlib import Path
import shutil
import tempfile
from fastapi import HTTPException

def _atomic_write(path, raw, overwrite):
    if path.exists() and (not overwrite):
        _fail('파일이 이미 존재합니다.', 409)
    if not path.parent.is_dir():
        _fail('부모 폴더가 없습니다.', 404)
    fd, tmp = tempfile.mkstemp(prefix='.pc-write-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(raw)
        _check_stop()
        if overwrite:
            os.replace(tmp, path)
        else:
            os.rename(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)

def _checked(raw, tree=False):
    text = str(raw)
    if text.startswith('temp:/'):
        root = config.DATA_DIR / 'tmp'
        root.mkdir(parents=True, exist_ok=True)
        path = (root / text[6:]).resolve()
        if not _within(path, root.resolve()):
            _fail('임시폴더 밖으로 이동할 수 없습니다.', 403)
    else:
        path = Path(text).expanduser().resolve()
    if ':' in str(path)[2:] or str(path).startswith(('\\\\.\\', '\\\\?\\')):
        _fail('장치/대체 데이터 스트림 경로는 허용하지 않습니다.', 403)
    if _within(path, config.PRIVATE.resolve()) or (tree and _within(config.PRIVATE.resolve(), path)):
        _fail('서버 내부 파일에는 접근할 수 없습니다.', 403)
    if path.is_file() and path.stat().st_nlink > 1:
        _fail('하드링크 파일은 허용하지 않습니다.', 403)
    allowed = (config.DATA_DIR / 'tmp').resolve()
    if _within(path, config.BASE_DIR.resolve()) and (not (allowed and _within(path, allowed))):
        _fail('서버 내부 파일에는 접근할 수 없습니다.', 403)
    if tree and _within(config.BASE_DIR.resolve(), path):
        _fail('서버 폴더를 포함한 재귀 작업은 허용하지 않습니다.', 403)
    if tree and path.is_dir():
        for folder, dirs, files in os.walk(path, followlinks=False):
            _check_stop()
            for name in dirs + files:
                child = Path(folder) / name
                if child.is_symlink() or (hasattr(child, 'is_junction') and child.is_junction()):
                    _fail('재귀 작업의 링크/junction은 허용하지 않습니다.', 403)
    return path

def _content(data):
    data = _options(data, {'text', 'base64', 'encoding'})
    if ('text' in data) == ('base64' in data):
        _fail('content에 text 또는 base64 하나를 지정하세요.')
    try:
        result = base64.b64decode(data['base64'], validate=True) if 'base64' in data else str(data['text']).encode(data.get('encoding', 'utf-8'))
    except (ValueError, LookupError):
        _fail('잘못된 인코딩 또는 base64입니다.')
    if len(result) > 32 * 1024 * 1024:
        _fail('한 번에 최대 32MB를 저장할 수 있습니다.', 413)
    return result

def _files(action, **kw):
    opts = _options(kw.get('options', {}), {'overwrite', 'recursive', 'encoding', 'offset', 'limit', 'expected_hash'})
    for flag in ('overwrite', 'recursive'):
        if flag in opts and (not isinstance(opts[flag], bool)):
            _fail(flag + '는 JSON true/false여야 합니다.')
    p = _checked(kw['path'], tree=action in ('move', 'copy', 'rename', 'delete'))
    if action == 'info':
        return _info(p)
    if action == 'list':
        offset = _number(opts.get('offset', 0), 0, integer=True)
        limit = _number(opts.get('limit', 200), 1, 2000, True)
        if not p.is_dir():
            _fail('폴더를 찾을 수 없습니다.', 404)
        result = []
        for child in sorted(p.iterdir()):
            try:
                result.append(_info(_checked(child)))
            except (PermissionError, FileNotFoundError):
                continue
            except Exception as exc:
                from fastapi import HTTPException
                if isinstance(exc, HTTPException) and exc.status_code == 403:
                    continue
                raise
        return {'items': result[offset:offset + limit], 'total': len(result)}
    if action == 'read':
        offset = _number(opts.get('offset', 0), 0, integer=True)
        limit = _number(opts.get('limit', 1024 * 1024), 1, 32 * 1024 * 1024, True)
        with p.open('rb') as f:
            f.seek(offset)
            raw = f.read(limit)
        encoding = opts.get('encoding', 'utf-8')
        return {'content': base64.b64encode(raw).decode() if encoding == 'base64' else raw.decode(encoding), 'encoding': encoding, 'bytes': len(raw), 'next_offset': offset + len(raw), 'eof': offset + len(raw) >= p.stat().st_size}
    _check_stop()
    if action == 'open':
        os.startfile(str(p))
        return {'opened': str(p)}
    if action == 'create' and kw['kind'] == 'directory':
        p.mkdir()
    elif action in ('create', 'save', 'edit'):
        if action == 'create' and kw['kind'] != 'file':
            _fail('kind는 file 또는 directory여야 합니다.')
        if action == 'edit':
            if not p.is_file():
                _fail('수정할 파일이 없습니다.', 404)
            expected = opts.get('expected_hash')
            if expected and hashlib.sha256(p.read_bytes()).hexdigest() != expected:
                _fail('파일 내용이 변경되었습니다.', 409)
        _atomic_write(p, _content(kw['content']), action == 'edit' or opts.get('overwrite', False))
    elif action in ('copy', 'move', 'rename'):
        if action == 'rename':
            name = str(kw['name'])
            if Path(name).name != name or '/' in name or '\\' in name or (name in ('.', '..')):
                _fail('이름만 지정하세요.')
            target = _checked(p.parent / name)
        else:
            target = _checked(kw['destination'])
        if p == target or (_within(target, p) and p.is_dir()):
            _fail('자기 자신 또는 하위 폴더를 대상으로 지정할 수 없습니다.')
        if target.exists():
            if not opts.get('overwrite', False) or p.is_dir() or target.is_dir():
                _fail('대상이 이미 존재합니다.', 409)
        if action == 'copy':
            if p.is_dir():

                def copy_file(source, destination):
                    _check_stop()
                    return shutil.copy2(_checked(source), _checked(destination))
                shutil.copytree(p, target, copy_function=copy_file)
            else:
                shutil.copy2(p, target)
        elif action == 'rename':
            os.replace(p, target) if opts.get('overwrite', False) else p.rename(target)
        elif target.exists():
            os.replace(p, target)
        else:
            shutil.move(str(p), str(target))
        return _info(target)
    elif action == 'delete':
        if p.is_dir():
            shutil.rmtree(p) if opts.get('recursive', False) else p.rmdir()
        else:
            p.unlink()
        return {'deleted': str(p)}
    return _info(p)

def _info(path):
    stat = path.stat()
    return {'path': str(path), 'name': path.name, 'directory': path.is_dir(), 'size': stat.st_size, 'modified': stat.st_mtime}

def _within(path, root):
    return path == root or root in path.parents

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
    opts = _options(kw.get('options', {}), {'overwrite', 'recursive', 'encoding', 'offset', 'limit', 'expected_hash'})
    for flag in ('overwrite', 'recursive'):
        if flag in opts and (not isinstance(opts[flag], bool)):
            _fail(flag + '는 JSON true/false여야 합니다.')
    p = _checked(kw['path'], tree='create' in ('move', 'copy', 'rename', 'delete'))
    _check_stop()
    if 'create' == 'create' and kw['kind'] == 'directory':
        p.mkdir()
    else:
        if 'create' == 'create' and kw['kind'] != 'file':
            _fail('kind는 file 또는 directory여야 합니다.')
        _atomic_write(p, _content(kw['content']), 'create' == 'edit' or opts.get('overwrite', False))
    return _info(p)
