import base64
import hashlib
import os
from pathlib import Path
import shutil
import tempfile
from core import runtime as rt


def within(path, root):
    return path == root or root in path.parents


def checked(raw, tree=False):
    text = str(raw)
    if text.startswith('temp:/'):
        root = rt.mission_dir() / 'tmp'
        root.mkdir(exist_ok=True)
        path = (root / text[6:]).resolve()
        if not within(path, root.resolve()):
            rt.fail('임시폴더 밖으로 이동할 수 없습니다.', 403)
    else:
        path = Path(text).expanduser().resolve()
    # Block NT device/alternate data stream paths and all server code/state.
    if ':' in str(path)[2:] or str(path).startswith(('\\\\.\\', '\\\\?\\')):
        rt.fail('장치/대체 데이터 스트림 경로는 허용하지 않습니다.', 403)
    if within(path, rt.PRIVATE.resolve()) or (tree and within(rt.PRIVATE.resolve(), path)):
        rt.fail('서버 내부 파일에는 접근할 수 없습니다.', 403)
    if path.is_file() and path.stat().st_nlink > 1:
        rt.fail('하드링크 파일은 허용하지 않습니다.', 403)
    allowed = None
    if rt.active:
        allowed = (rt.DATA / 'missions' / rt.current()['id'] / 'tmp').resolve()
    if within(path, rt.BASE.resolve()) and not (allowed and within(path, allowed)):
        rt.fail('서버 내부 파일에는 접근할 수 없습니다.', 403)
    if tree and within(rt.BASE.resolve(), path):
        rt.fail('서버 폴더를 포함한 재귀 작업은 허용하지 않습니다.', 403)
    if tree and path.is_dir():
        for folder, dirs, files in os.walk(path, followlinks=False):
            rt.check_stop()
            for name in dirs + files:
                child = Path(folder) / name
                if child.is_symlink() or (hasattr(child, 'is_junction') and child.is_junction()):
                    rt.fail('재귀 작업의 링크/junction은 허용하지 않습니다.', 403)
    return path


def content(data):
    data = rt.options(data, {'text', 'base64', 'encoding'})
    if ('text' in data) == ('base64' in data):
        rt.fail('content에 text 또는 base64 하나를 지정하세요.')
    try:
        result = base64.b64decode(data['base64'], validate=True) if 'base64' in data else str(data['text']).encode(data.get('encoding', 'utf-8'))
    except (ValueError, LookupError):
        rt.fail('잘못된 인코딩 또는 base64입니다.')
    if len(result) > 32*1024*1024:
        rt.fail('한 번에 최대 32MB를 저장할 수 있습니다.', 413)
    return result


def info(path):
    stat = path.stat()
    return {'path': str(path), 'name': path.name, 'directory': path.is_dir(), 'size': stat.st_size, 'modified': stat.st_mtime}


def atomic_write(path, raw, overwrite):
    if path.exists() and not overwrite:
        rt.fail('파일이 이미 존재합니다.', 409)
    if not path.parent.is_dir():
        rt.fail('부모 폴더가 없습니다.', 404)
    fd, tmp = tempfile.mkstemp(prefix='.pc-write-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(raw)
        rt.check_stop()
        if overwrite:
            os.replace(tmp, path)
        else:
            # Windows rename refuses an existing destination (no overwrite race).
            os.rename(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def files(action, **kw):
    opts = rt.options(kw.get('options', {}), {'overwrite', 'recursive', 'encoding', 'offset', 'limit', 'expected_hash'})
    for flag in ('overwrite', 'recursive'):
        if flag in opts and not isinstance(opts[flag], bool):
            rt.fail(flag+'는 JSON true/false여야 합니다.')
    p = checked(kw['path'], tree=action in ('move', 'copy', 'rename', 'delete'))
    if action == 'info':
        return info(p)
    if action == 'list':
        offset = rt.number(opts.get('offset', 0), 0, integer=True)
        limit = rt.number(opts.get('limit', 200), 1, 2000, True)
        if not p.is_dir():
            rt.fail('폴더를 찾을 수 없습니다.', 404)
        result = []
        for child in sorted(p.iterdir()):
            try:
                result.append(info(checked(child)))
            except (PermissionError, FileNotFoundError):
                continue
            except Exception as exc:
                from fastapi import HTTPException
                if isinstance(exc, HTTPException) and exc.status_code == 403:
                    continue
                raise
        return {'items': result[offset:offset+limit], 'total': len(result)}
    if action == 'read':
        offset = rt.number(opts.get('offset', 0), 0, integer=True)
        limit = rt.number(opts.get('limit', 1024*1024), 1, 32*1024*1024, True)
        with p.open('rb') as f:
            f.seek(offset)
            raw = f.read(limit)
        encoding = opts.get('encoding', 'utf-8')
        return {'content': base64.b64encode(raw).decode() if encoding == 'base64' else raw.decode(encoding),
                'encoding': encoding, 'bytes': len(raw), 'next_offset': offset+len(raw), 'eof': offset+len(raw)>=p.stat().st_size}
    rt.check_stop()
    if action == 'open':
        os.startfile(str(p))
        return {'opened': str(p)}
    if action == 'create' and kw['kind'] == 'directory':
        p.mkdir()
    elif action in ('create','save','edit'):
        if action == 'create' and kw['kind'] != 'file':
            rt.fail('kind는 file 또는 directory여야 합니다.')
        if action == 'edit':
            if not p.is_file():
                rt.fail('수정할 파일이 없습니다.', 404)
            expected = opts.get('expected_hash')
            if expected and hashlib.sha256(p.read_bytes()).hexdigest() != expected:
                rt.fail('파일 내용이 변경되었습니다.', 409)
        atomic_write(p, content(kw['content']), action == 'edit' or opts.get('overwrite', False))
    elif action in ('copy', 'move', 'rename'):
        if action == 'rename':
            name = str(kw['name'])
            if Path(name).name != name or '/' in name or '\\' in name or name in ('.','..'):
                rt.fail('이름만 지정하세요.')
            target = checked(p.parent / name)
        else:
            target = checked(kw['destination'])
        if p == target or within(target, p) and p.is_dir():
            rt.fail('자기 자신 또는 하위 폴더를 대상으로 지정할 수 없습니다.')
        if target.exists():
            if not opts.get('overwrite', False) or p.is_dir() or target.is_dir():
                rt.fail('대상이 이미 존재합니다.', 409)
        if action == 'copy':
            if p.is_dir():
                def copy_file(source, destination):
                    rt.check_stop()
                    return shutil.copy2(checked(source), checked(destination))
                shutil.copytree(p, target, copy_function=copy_file)
            else:
                shutil.copy2(p, target)
        elif action == 'rename':
            os.replace(p, target) if opts.get('overwrite', False) else p.rename(target)
        else:
            if target.exists():
                os.replace(p, target)
            else:
                shutil.move(str(p), str(target))
        return info(target)
    elif action == 'delete':
        if p.is_dir():
            shutil.rmtree(p) if opts.get('recursive', False) else p.rmdir()
        else:
            p.unlink()
        return {'deleted': str(p)}
    return info(p)


def temp():
    path = rt.mission_dir() / 'tmp'
    path.mkdir(exist_ok=True)
    return {'path': str(path), 'alias': 'temp:/', 'mission_id': rt.current()['id']}
