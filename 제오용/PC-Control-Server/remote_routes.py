import base64
import capture_store
import json
from fastapi import APIRouter,Request,HTTPException
from fastapi.responses import JSONResponse,Response
from starlette.concurrency import run_in_threadpool
from remote.client import request as remote_request,ALLOWED_PATHS
router=APIRouter()
async def forward(request:Request):
    try:
        data=dict(request.query_params)
        if request.method=='POST':
            raw=await request.body()
            body=json.loads(raw) if raw else {}
            if not isinstance(body,dict): raise ValueError()
            data.update(body)
        for key,value in list(data.items()):
            if isinstance(value,str) and value.startswith(('{','[')):
                try: data[key]=json.loads(value)
                except ValueError: pass
        result=await run_in_threadpool(remote_request,request.url.path,data,request.method)
        if 'response' in result: return JSONResponse(result['response'])
        raw = capture_store.read(result) if result.get('encoding') == 'local_file' else base64.b64decode(result['data'])
        return Response(raw,media_type=result['content_type'])
    except OSError: return JSONResponse({'success':False,'error':'제어 PC 임시 이미지 파일을 읽을 수 없습니다.'},status_code=502)
    except (ValueError,UnicodeError): return JSONResponse({'success':False,'error':'JSON 객체가 필요합니다.'},status_code=400)
    except HTTPException as exc: return JSONResponse({'success':False,'error':exc.detail},status_code=exc.status_code)
for path in sorted(ALLOWED_PATHS):
    for method in ('GET','POST'): router.add_api_route(path,forward,methods=[method],operation_id=method.lower()+path.replace('/','_'))
