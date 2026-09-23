"""Internal-only HTTP audit. No endpoint exposes this file."""
import hashlib
import json
import re
import threading
import time
from core import runtime as rt

_guard = threading.Lock()
_SECRET = re.compile(r'password|passwd|secret|token|authorization|cookie|api[_-]?key|user[_-]?key', re.I)


def redact(value):
    if isinstance(value, dict):
        return {k: '[REDACTED]' if _SECRET.search(str(k)) else redact(v) for k,v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    if isinstance(value, str):
        keypath = rt.PRIVATE / 'user.key'
        if keypath.exists():
            key = keypath.read_text(encoding='utf-8')
            if key:
                value = value.replace(key, '[REDACTED]')
        return value
    return value


def summarize(raw, total, content_type):
    if 'image/' in content_type or 'octet-stream' in content_type:
        return {'content_type':content_type,'bytes':total}
    try:
        return redact(json.loads(raw))
    except (ValueError, UnicodeDecodeError):
        # Unparseable raw bodies may contain credentials. Do not dump raw text.
        return {'bytes':total,'truncated':total>len(raw),'unparsed':True}


class Audit:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope,receive,send)
        start = time.monotonic()
        request_id = rt.uid()
        request = bytearray()
        response = bytearray()
        req_size = res_size = 0
        status = 500
        mime = ''
        exception = None
        async def recv():
            nonlocal req_size
            message = await receive()
            chunk = message.get('body',b'')
            req_size += len(chunk)
            request.extend(chunk[:max(0,65536-len(request))])
            return message
        async def emit(message):
            nonlocal res_size,status,mime
            if message['type'] == 'http.response.start':
                status = message['status']
                headers = list(message.get('headers',[]))
                headers.append((b'x-request-id',request_id.encode()))
                mime = dict(headers).get(b'content-type',b'').decode()
                message = {**message,'headers':headers}
            if message['type'] == 'http.response.body':
                chunk = message.get('body',b'')
                res_size += len(chunk)
                response.extend(chunk[:max(0,65536-len(response))])
            await send(message)
        try:
            await self.app(scope,recv,emit)
        except Exception as exc:
            exception = type(exc).__name__
            raise
        finally:
            from urllib.parse import parse_qs
            duration = (time.monotonic()-start)*1000
            data = {'timestamp':rt.timestamp(),'request_id':request_id,'method':scope['method'],
                    'path':scope['path'],'parameters':redact(parse_qs(scope.get('query_string',b'').decode(errors='replace'))),
                    'body':summarize(bytes(request),req_size,'application/json'),
                    'response':summarize(bytes(response),res_size,mime), 'status':status,
                    'duration_ms':round(duration,3),'error':scope.get('execution_error',exception)}
            if status >= 400 and data['error'] is None:
                data['error'] = data['response']
            rt.init()
            with _guard:
                rt.stats['requests'] += 1
                rt.stats['errors'] += int(status >= 400)
                rt.stats['duration_ms'] += duration
                with (rt.PRIVATE/'server.jsonl').open('a',encoding='utf-8') as f:
                    f.write(json.dumps(data,ensure_ascii=False)+'\n')
