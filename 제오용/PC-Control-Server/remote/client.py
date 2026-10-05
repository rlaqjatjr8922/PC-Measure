import base64
import json
import httpx
from fastapi import HTTPException
from remote import resolver
import api_config
import capture_store
GROUPS=('mouse','keyboard','window','system','files','temp','screen','verify','watch','interaction','safety','input','recording','macro')
ALLOWED_PATHS=frozenset('/'+g+'/'+f for g in GROUPS for f in getattr(api_config,g))

def request(path,parameters=None,method='POST'):
    if path not in ALLOWED_PATHS or method not in ('GET','POST') or (parameters is not None and not isinstance(parameters,dict)):
        raise HTTPException(400,'잘못된 원격 경로, 방식 또는 매개변수')
    try: endpoint=resolver.resolve()
    except RuntimeError as exc: raise HTTPException(503,str(exc)) from None
    parameters={} if parameters is None else parameters
    for attempt in range(2):
        try:
            with httpx.Client(timeout=3600 if path == '/macro/run' else int(parameters.get('timeout',60))+40 if path == '/system/powershell' else 30,follow_redirects=False) as client:
                kwargs={'json':parameters} if method=='POST' else {'params':{k:json.dumps(v) if isinstance(v,(dict,list)) else v for k,v in parameters.items()}}
                response=client.request(method,endpoint['base_url']+path,**kwargs)
            if response.status_code>=500: raise HTTPException(502,'Upstream server error')
            if response.status_code>=300:
                try: reason=response.json().get('error',response.json().get('reason','원격 요청 실패'))
                except (ValueError,AttributeError): reason='원격 요청 실패'
                raise HTTPException(response.status_code,str(reason))
            resolver.confirmed(endpoint)
            result=dict(base_url=endpoint['base_url'],path=path,status_code=response.status_code)
            if 'json' in response.headers.get('content-type',''):
                result['response']=response.json()
            else:
                content_type = response.headers.get('content-type', 'application/octet-stream')
                if content_type.split(';')[0].strip().startswith('image/'):
                    # Store on this controller PC, never via a remote files/save call.
                    try:
                        result.update(capture_store.save(response.content, content_type))
                    except (OSError, ValueError) as exc:
                        raise HTTPException(502, '제어 PC 임시 이미지 저장 실패: ' + type(exc).__name__) from None
                else:
                    result.update(encoding='base64',content_type=content_type,bytes=len(response.content),data=base64.b64encode(response.content).decode())
            return result
        except httpx.HTTPError as exc:
            # A read timeout may mean a click/write already ran; never replay an ambiguous action.
            retryable=isinstance(exc,(httpx.ConnectError,httpx.ConnectTimeout))
            try: refreshed=resolver.resolve(force=True)
            except RuntimeError: refreshed=endpoint
            if attempt==0 and retryable and refreshed['base_url']!=endpoint['base_url']:
                endpoint=refreshed; continue
            raise HTTPException(504 if isinstance(exc,httpx.TimeoutException) else 502,'원격 연결 실패') from None
        except ValueError:
            raise HTTPException(502,'원격 JSON 응답 오류') from None
