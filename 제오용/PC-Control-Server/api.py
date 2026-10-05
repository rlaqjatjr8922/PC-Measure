import importlib.util
import json
import logging
from pathlib import Path
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
import api_config
from threading import RLock

router = APIRouter()
PLUGIN_DIR = Path(__file__).resolve().parent / 'plugins'
MCP_DIR = Path(__file__).resolve().parent / 'mcp'
from measure_tools import REMOTE_GROUPS, schema as measure_schema, validated as measure_validated
LOCK = RLock()
CONFIG_PATH = Path(api_config.__file__)


def read_api_config():
    # Read source directly: same-second edits must not reuse stale .pyc files.
    namespace = {'__file__': str(CONFIG_PATH), '__name__': 'api_config'}
    exec(compile(CONFIG_PATH.read_bytes(), str(CONFIG_PATH), 'exec'), namespace)
    return namespace



def validate_params(schema, data):
    if set(data) - set(schema):
        raise ValueError('알 수 없는 매개변수: ' + ', '.join(sorted(set(data) - set(schema))))
    params = {}
    for key, default in schema.items():
        value = data.get(key, default)
        if value is ...:
            raise ValueError('필수 값이 없습니다: ' + key)
        if value is None and default is None:
            continue
        if key in ('enabled', 'save_request', 'save_response', 'save_error', 'save_reject'):
            if isinstance(value, str) and value.lower() in ('true', 'false'):
                value = value.lower() == 'true'
            if not isinstance(value, bool):
                raise ValueError(key + '에는 true 또는 false를 입력하세요.')
        elif key in ('direction', 'limit', 'max_days'):
            if isinstance(value, str):
                try:
                    value = int(value)
                except ValueError:
                    raise ValueError(key + '에는 정수를 입력하세요.')
            if type(value) is not int:
                raise ValueError(key + '에는 정수를 입력하세요.')
            if key == 'direction' and value not in (-1, 1):
                raise ValueError('direction은 -1 또는 1이어야 합니다.')
            if key != 'direction' and value < 1:
                raise ValueError(key + '는 1 이상이어야 합니다.')
        elif isinstance(default, dict):
            if isinstance(value, str):
                try:
                    value = json.loads(value)
                except ValueError:
                    raise ValueError(key + '은 JSON 객체여야 합니다.')
            if not isinstance(value, dict):
                raise ValueError(key + '은 JSON 객체여야 합니다.')
        elif key == 'plan':
            if isinstance(value, str):
                try:
                    value = json.loads(value)
                except ValueError:
                    raise ValueError('plan은 단계 문자열의 JSON 배열이어야 합니다.')
            if not isinstance(value, list) or not value or any(not isinstance(step, str) or not step.strip() for step in value):
                raise ValueError('plan은 비어 있지 않은 단계 문자열 배열이어야 합니다.')
        else:
            if not isinstance(value, str) or (not value.strip() and key not in ('query', 'mission_id')):
                raise ValueError(key + '에는 비어 있지 않은 문자열을 입력하세요.')
            if key == 'mission_id' and value:
                load_plugin('history', 'detail').mission_path(value)
            elif key == 'mission_id' and default is ...:
                raise ValueError('mission_id가 필요합니다.')
        choices = {'scope': ('step', 'mission'), 'type': ('all', 'request', 'response', 'error', 'reject'),
                   'status': ('all', 'working', 'completed')}
        if key in choices and value not in choices[key]:
            raise ValueError(key + ' 값이 올바르지 않습니다.')
        params[key] = value
    return params

def load_plugin(group, feature):
    path = MCP_DIR / group / (feature + '.py')
    if not path.is_file():
        path = PLUGIN_DIR / group / (feature + '.py')
    spec = importlib.util.spec_from_file_location('plugin_' + group + '_' + feature, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def safe_log(kind, payload, mid, path):
    try:
        load_plugin('log', 'config').log(kind, payload, mid, path)
    except Exception:
        logging.exception('API 로그 저장 실패')

def dispatch(group, feature, data, path, parse_error=None):
    with LOCK:
        mid = data.get('mission_id')
        if group == 'mission':
            mid = load_plugin('history', 'detail').current_id()
        safe_log('request', data, mid, path)
        try:
            group_config = read_api_config().get(group)
            if not isinstance(group_config, dict) or feature not in group_config:
                raise FileNotFoundError('등록되지 않은 API입니다.')
            if parse_error:
                raise ValueError(parse_error)
            params = validate_params(group_config[feature], data)
            result = load_plugin(group, feature).run(**params)
            if isinstance(result, dict):
                mid = result.get('mission_id', mid)
            body, status = {'success': True, 'result': result}, 200
        except HTTPException as exc:
            body, status = {'success': False, 'reason': exc.detail}, exc.status_code
            safe_log('error', body, mid, path)
        except (ValueError, FileNotFoundError) as exc:
            status = 404 if isinstance(exc, FileNotFoundError) else 400
            body = {'success': False, 'reason': str(exc)}
            safe_log('error', body, mid, path)
        except Exception:
            logging.exception('API 처리 실패')
            body, status = {'success': False, 'reason': '서버 내부 오류가 발생했습니다.'}, 500
            safe_log('error', body, mid, path)
        # Avoid recursively embedding previous logs in log/view response logs.
        logged_body = {'success': True, 'count': result['count']} if status == 200 and group == 'log' and feature == 'view' else body
        safe_log('response', logged_body, mid, path)
        return JSONResponse(content=body, status_code=status)

async def execute(group, feature, request):
    error = None
    if request.method == 'GET':
        data = dict(request.query_params)
    else:
        try:
            raw = await request.body()
            data = json.loads(raw) if raw else {}
            if not isinstance(data, dict):
                raise ValueError()
        except (ValueError, UnicodeDecodeError):
            data, error = {}, '요청 본문은 JSON 객체여야 합니다.'
    return await run_in_threadpool(dispatch, group, feature, data, request.url.path, error)

@router.api_route('/remote/{feature}', methods=['GET', 'POST'])
async def remote_api(feature: str, request: Request):
    return await execute('remote', feature, request)

@router.api_route('/history/{feature}', methods=['GET', 'POST'])
async def history_api(feature: str, request: Request):
    return await execute('history', feature, request)

@router.api_route('/log/{feature}', methods=['GET', 'POST'])
async def log_api(feature: str, request: Request):
    return await execute('log', feature, request)

@router.api_route('/mcp/mission/{feature}', methods=['GET', 'POST'])
async def mission_api(feature: str, request: Request):
    return await execute('mission', feature, request)

# MCP tool definitions and calls share the live api_config.py configuration.
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import Tool, CallToolResult, TextContent
from jsonschema import validate as validate_json_schema, ValidationError


def tool_schema(params, group=None, feature=None):
    if group in REMOTE_GROUPS:
        return measure_schema(params, '/' + group + '/' + feature)
    properties, required = {}, []
    for key, default in params.items():
        if key in ('direction', 'limit', 'max_days') or type(default) is int:
            field = {'type': 'integer'}
        elif key in ('enabled', 'save_request', 'save_response', 'save_error', 'save_reject') or type(default) is bool:
            field = {'type': 'boolean'}
        elif type(default) is float:
            field = {'type': 'number'}
        elif key == 'plan' or isinstance(default, list):
            field = {'type': 'array', 'items': {'type': 'string'}, 'minItems': 1}
        elif isinstance(default, dict):
            field = {'type': 'object', 'additionalProperties': True}
        else:
            field = {'type': 'string', 'minLength': 1}
        if key == 'direction':
            field['enum'] = [-1, 1]
        elif key == 'scope':
            field['enum'] = ['step', 'mission']
        elif key == 'status':
            field['enum'] = ['all', 'working', 'completed']
        elif key == 'type':
            field['enum'] = ['all', 'request', 'response', 'error', 'reject']
        elif key in ('limit', 'max_days'):
            field['minimum'] = 1
        if key in ('query', 'mission_id'):
            field.pop('minLength', None)
        if default is None:
            field['type'] = [field['type'], 'null']
            if 'enum' in field:
                field['enum'].append(None)
        if default is ...:
            required.append(key)
        elif default is not None:
            field['default'] = default
        properties[key] = field
    return dict(type='object', properties=properties, required=required, additionalProperties=False)


def configured_tools(settings):
    """Build the complete registry from config, without retaining removed tools."""
    registry = {}
    for group, features in settings.items():
        if group.startswith('_') or group.endswith('_descriptions'):
            continue
        if not isinstance(features, dict):
            continue
        descriptions = settings.get(group + '_descriptions', {})
        for feature, params in features.items():
            if not isinstance(params, dict):
                continue
            name = group + '_' + feature
            if name in settings.get('_mcp_excluded', set()):
                continue
            if name in registry:
                raise ValueError('중복된 MCP 도구 이름입니다: ' + name)
            registry[name] = (group, feature, params,
                              descriptions.get(feature, group + '의 ' + feature + ' 기능을 실행합니다.'))
    return registry


class ConfigMCP(MCPServer):
    async def list_tools(self):
        def build():
            with LOCK:
                settings = read_api_config()
                return [Tool(name=name, description=description,
                             input_schema=tool_schema(params,group,feature))
                        for name,(group,feature,params,description) in configured_tools(settings).items()]
        return await run_in_threadpool(build)

    async def call_tool(self,name,arguments,context=None):
        def call():
            with LOCK:
                registry=configured_tools(read_api_config())
                if name not in registry:
                    raise ToolError('reason: 등록되지 않은 MCP 도구입니다: '+name)
                group,feature,params,description=registry[name]
            data={} if arguments is None else arguments
            if group in REMOTE_GROUPS:
                try:
                    normalized=measure_validated(params,data,'/'+group+'/'+feature)
                    # No global lock during remote I/O: emergency stop can interrupt a long operation.
                    result=load_plugin(group,feature).run(**normalized)
                except ValueError as exc:
                    raise ToolError(str(exc)) from exc
                except HTTPException as exc:
                    raise ToolError('reason: '+str(exc.detail)) from exc
            else:
                try:
                    validate_json_schema(data,tool_schema(params,group,feature))
                except ValidationError as exc:
                    raise ToolError('reason: 잘못된 도구 입력: '+exc.message) from exc
                response=dispatch(group,feature,data,'/mcp')
                body=json.loads(response.body)
                if not body['success']:
                    raise ToolError('reason: '+body['reason'])
                result=body['result']
            from image_result import build
            try:
                return build(result)
            except (ValueError, OSError) as exc:
                raise ToolError('이미지 응답을 처리할 수 없습니다: '+str(exc)) from exc
        return await run_in_threadpool(call)


mcp = ConfigMCP(
    'PC Control Server',
    instructions='작업 이력·상태·단계·로그를 관리합니다. remote_status로 연결된 PC를 확인하고 mouse_click, keyboard_type 등 각 기능의 개별 도구로 요청한 PC Measure API를 호출합니다.',
)
mcp_app = mcp.streamable_http_app(
    host='0.0.0.0',
    streamable_http_path='/mcp',
    stateless_http=True,
    json_response=True,
)
