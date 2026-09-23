from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from starlette.concurrency import run_in_threadpool
import secrets
import config
import api_config
from core import runtime as rt
from core.audit import Audit, redact
from core.dispatch import execute
from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app):
    rt.init()
    try:
        yield
    finally:
        await run_in_threadpool(rt.stop, '서버 종료')

app = FastAPI(title='PC Control Server', lifespan=lifespan)
app.add_middleware(Audit)
BASE_DIR = rt.BASE


def get_feature_config(group, feature):
    group_config = getattr(api_config, group, None)
    if not isinstance(group_config, dict) or feature not in group_config:
        raise HTTPException(404, 'api_config.py에 등록되지 않은 기능입니다.')
    return group_config[feature]


def remove_empty_request_values(data):
    return {k:v for k,v in data.items() if v is not None and v != ''}


def build_arguments(feature_config, request_values):
    arguments = {}
    if 'mode' in feature_config:
        modes = feature_config['mode']
        mode = request_values.get('mode')
        if mode is None and len(modes) == 1:
            mode = next(iter(modes))
        if not isinstance(mode,str) or mode not in modes:
            raise HTTPException(400, {'error':'올바른 mode가 필요합니다.','available_modes':list(modes)})
        arguments['mode'] = mode
        fields = modes[mode]
    else:
        fields = feature_config
    unknown = set(request_values)-set(fields)-({'mode'} if 'mode' in feature_config else set())
    if unknown:
        raise HTTPException(400, {'error':'등록되지 않은 호출값입니다.','unknown':sorted(unknown)})
    missing = []
    for key, default in fields.items():
        value = request_values.get(key,default)
        if value is None or value == '':
            missing.append(key)
        else:
            arguments[key] = value
    if missing:
        raise HTTPException(400, {'error':'필수 호출값이 비어 있습니다.','missing':missing})
    return arguments


@app.exception_handler(HTTPException)
async def http_error(request, error):
    return JSONResponse({'success':False,'error':redact(error.detail)}, status_code=error.status_code)


@app.exception_handler(RequestValidationError)
async def validation_error(request, error):
    return JSONResponse({'success':False,'error':'잘못된 요청 형식입니다.'}, status_code=422)


@app.api_route('/{group}/{feature}', methods=['GET','POST'])
async def run_feature(group: str, feature: str, request: Request):
    if not group.replace('_','').isalnum() or not feature.replace('_','').isalnum():
        raise HTTPException(400,'잘못된 기능 경로입니다.')
    feature_config = get_feature_config(group,feature)
    origin = request.headers.get('origin')
    if origin and origin not in ('http://127.0.0.1:8000','http://localhost:8000'):
        raise HTTPException(403,'다른 웹사이트에서 호출할 수 없습니다.')
    # Only the local user/client gets this key. Never include it in model arguments.
    user_only = group == 'history' or group == 'interaction' and feature in ('answer','questions')
    if user_only and not secrets.compare_digest(request.headers.get('x-user-key',''), rt.user_key()):
        raise HTTPException(403,'사용자 전용 기능입니다.')
    values = dict(request.query_params)
    if request.method == 'POST':
        raw = await request.body()
        if len(raw) > 48*1024*1024:
            raise HTTPException(413,'요청이 너무 큽니다.')
        if raw:
            try:
                body = await request.json()
            except ValueError:
                raise HTTPException(400,'올바른 JSON이 필요합니다.')
            if not isinstance(body,dict):
                raise HTTPException(400,'JSON 객체가 필요합니다.')
            values.update(body)
    arguments = build_arguments(feature_config,remove_empty_request_values(values))
    supplied_context = request.headers.get('x-mission-context')
    if supplied_context and (not rt.active or supplied_context != rt.active['generation']):
        raise HTTPException(409,'이전 Mission 연결입니다.')
    public_status = group == 'system' and feature in ('status','info','telemetry')
    user_authenticated = secrets.compare_digest(request.headers.get('x-user-key',''), rt.user_key())
    if not user_only and group != 'safety' and not public_status:
        if not rt.active:
            raise HTTPException(409,'사용자가 먼저 Mission을 선택해야 합니다.')
        if not supplied_context and not user_authenticated:
            raise HTTPException(409,'선택 응답의 X-Mission-Context가 필요합니다.')
    token = rt.context.set(dict(rt.active) if rt.active else None)
    try:
        # All selected-work data is bound once per request, including worker threads.
        if group in ('mission','temp','macro','watch','interaction'):
            rt.current()
        if group == 'history':
            from core import macros
            if macros.recording or macros.replaying:
                if feature in ('create','select'):
                    raise HTTPException(409,'매크로 기록/재생을 먼저 중지하세요.')
        # Calls are off the event loop so stop/status remain responsive.
        result = await run_in_threadpool(execute,group,feature,arguments)
        if isinstance(result,bytes):
            mime = 'image/png' if result.startswith(b'\x89PNG') else 'image/jpeg' if result.startswith(b'\xff\xd8') else 'application/octet-stream'
            return Response(result,media_type=mime)
        return JSONResponse({'success':True,'group':group,'feature':feature,'result':redact(result)})
    except HTTPException:
        raise
    except FileNotFoundError:
        raise HTTPException(404,'파일을 찾을 수 없습니다.')
    except FileExistsError:
        raise HTTPException(409,'대상이 이미 존재합니다.')
    except PermissionError:
        raise HTTPException(403,'접근 권한이 없습니다.')
    except (ValueError,TypeError,KeyError,UnicodeError) as exc:
        raise HTTPException(400, '호출값 오류: '+type(exc).__name__)
    except Exception as exc:
        # Internal implementation details and credentials are not returned to GPT.
        import traceback
        request.scope['execution_error'] = redact(traceback.format_exc())
        raise HTTPException(500,'기능 실행 실패: '+type(exc).__name__)
    finally:
        rt.context.reset(token)


def select_startup_mission():
    from core.missions import history

    rt.init()
    print('\n========================================')
    print(' PC-Control-Server')
    print('========================================')

    while True:
        missions = history('list')
        print('\n작업을 선택하세요.\n')
        for index, mission in enumerate(missions, start=1):
            print(f"{index}. {mission['name']}")
        print('0. 새 작업\n')

        choice = input('선택 > ').strip()
        if not choice.isascii() or not choice.isdecimal():
            print('목록에 있는 번호를 입력하세요.')
            continue
        # Compare displayed labels instead of converting arbitrarily long input.
        if choice == '0':
            name = input('새 작업 이름 > ').strip()
            if not name or len(name) > 120:
                print('작업 이름은 1~120자로 입력하세요.')
                continue
            selected = history('create', name=name)
        else:
            index = next((i for i in range(len(missions)) if choice == str(i + 1)), None)
            if index is None:
                print('목록에 있는 번호를 입력하세요.')
                continue
            selected = history('select', mission_id=missions[index]['id'])

        print(f"\n선택한 작업: {selected['mission']['name']}")
        return selected


def main():
    import uvicorn

    try:
        select_startup_mission()
    except (EOFError, KeyboardInterrupt):
        print('\n작업 선택을 취소했습니다. 서버를 시작하지 않습니다.')
        return
    uvicorn.run(app,host=config.HOST,port=config.PORT)


if __name__ == '__main__':
    main()
