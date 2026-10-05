from pathlib import Path
from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, JSONResponse
from api import mcp
from mcp.server.mcpserver.exceptions import ToolError
router = APIRouter()

@router.get('/control')
async def control_page():
    return FileResponse(Path(__file__).parent/'static'/'control.html')

@router.get('/control/tools')
async def control_tools():
    return {'tools': [{'name': t.name, 'description': t.description, 'schema': t.input_schema} for t in await mcp.list_tools()]}

@router.post('/control/call')
async def control_call(request: Request):
    origin=request.headers.get('origin')
    if origin and origin.rstrip('/') != str(request.base_url).rstrip('/'):
        return JSONResponse({'ok':False,'error':'다른 사이트에서의 조작 요청은 허용하지 않습니다.'},403)
    if request.headers.get('x-pc-control')!='1':
        return JSONResponse({'ok':False,'error':'제어 화면에서 실행해 주세요.'},403)
    try:
        data=await request.json()
        if not isinstance(data,dict) or not isinstance(data.get('name'),str) or not isinstance(data.get('arguments',{}),dict):
            raise ValueError('올바른 입력이 필요합니다.')
        result=await mcp.call_tool(data['name'],data.get('arguments',{}))
        return {'ok':True,'result':result.structured_content, 'images':[{'data':c.data,'content_type':c.mime_type} for c in result.content if c.type=='image']}
    except (ToolError,ValueError) as exc:
        return JSONResponse({'ok':False,'error':str(exc)},400)
    except Exception:
        return JSONResponse({'ok':False,'error':'요청 처리 실패. 서버 연결 상태와 입력값을 확인하세요.'},502)
