"""등록된 /그룹/기능 요청을 해당 파일의 run()으로 전달합니다."""
import importlib.util
import json
import time
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from starlette.concurrency import run_in_threadpool
import api_config
import config

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app):
    import activity
    if activity.settings()['scope'] == 'all':
        activity.configure('program')
    yield
    import watch_engine
    watch_engine.shutdown()
    activity.stop_listeners()

app = FastAPI(lifespan=lifespan, title='PC Measure', docs_url=None, redoc_url=None, openapi_url=None)
BASE_DIR = Path(__file__).resolve().parent


@app.middleware('http')
async def request_statistics(request, call_next):
    started = time.monotonic()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        with config.lock:
            config.stats['requests'] += 1
            config.stats['errors'] += int(status >= 400)
            config.stats['duration_ms'] += (time.monotonic() - started) * 1000


def _execute(group, feature, values):
    schema = getattr(api_config, group, None)
    if group.startswith('_') or not isinstance(schema, dict) or feature not in schema:
        raise HTTPException(404, '등록되지 않은 기능입니다.')
    schema = schema[feature]
    arguments = {}
    if 'mode' in schema:
        modes = schema['mode']
        mode = values.get('mode', next(iter(modes)) if len(modes) == 1 else None)
        if not isinstance(mode, str) or mode not in modes:
            raise HTTPException(400, '올바른 mode가 필요합니다.')
        arguments['mode'] = mode
        schema = modes[mode]
    if set(values) - set(schema) - set(arguments):
        raise HTTPException(400, '등록되지 않은 입력값입니다.')
    for key, default in schema.items():
        value = values.get(key, default)
        if value is None or value == '':
            raise HTTPException(400, '필수 값이 없습니다: ' + key)
        if isinstance(default, (dict, list)) and isinstance(value, str):
            value = json.loads(value)
        arguments[key] = value
    path = (BASE_DIR / group / (feature + '.py')).resolve()
    if not path.is_relative_to(BASE_DIR) or not path.is_file():
        raise HTTPException(404, '기능 파일을 찾을 수 없습니다.')
    spec = importlib.util.spec_from_file_location('feature_' + group + '_' + feature, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.run(**arguments)


def execute(group, feature, values):
    import activity
    started = activity.now()
    result = None
    success = False
    error = None
    try:
        result = _execute(group, feature, values)
        success = not isinstance(result, dict) or result.get('success') is not False
        return result
    except Exception as exc:
        error = str(getattr(exc, 'detail', exc))
        raise
    finally:
        if group not in ('recording', 'macro'):
            try:
                activity.record('/'+group+'/'+feature, values, success, error=error, event_time=started)
            except Exception:
                import logging
                logging.exception('작업 로그 저장 실패')


@app.api_route('/{group}/{feature}', methods=['GET', 'POST'])
async def run_feature(group: str, feature: str, request: Request):
    try:
        if not group.replace('_', '').isalnum() or not feature.replace('_', '').isalnum():
            raise HTTPException(400, '잘못된 기능 경로입니다.')
        values = dict(request.query_params)
        if request.method == 'POST':
            raw = await request.body()
            if len(raw) > 48 * 1024 * 1024:
                raise HTTPException(413, '요청이 너무 큽니다.')
            if raw:
                body = json.loads(raw)
                if not isinstance(body, dict):
                    raise HTTPException(400, 'JSON 객체가 필요합니다.')
                values.update(body)
        result = await run_in_threadpool(execute, group, feature, values)
        if isinstance(result, bytes):
            mime = 'image/png' if result.startswith(b'\x89PNG') else 'image/jpeg' if result.startswith(b'\xff\xd8') else 'application/octet-stream'
            return Response(result, media_type=mime)
        return JSONResponse({'success': True, 'group': group, 'feature': feature, 'result': result})
    except HTTPException as exc:
        return JSONResponse({'success': False, 'error': exc.detail}, status_code=exc.status_code)
    except FileNotFoundError:
        return JSONResponse({'success': False, 'error': '파일을 찾을 수 없습니다.'}, status_code=404)
    except FileExistsError:
        return JSONResponse({'success': False, 'error': '대상이 이미 존재합니다.'}, status_code=409)
    except PermissionError:
        return JSONResponse({'success': False, 'error': '접근 권한이 없습니다.'}, status_code=403)
    except (ValueError, TypeError, KeyError, UnicodeError) as exc:
        return JSONResponse({'success': False, 'error': '잘못된 입력: ' + type(exc).__name__}, status_code=400)
    except Exception:
        return JSONResponse({'success': False, 'error': '기능 실행 실패'}, status_code=500)


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host=config.HOST, port=config.PORT)
