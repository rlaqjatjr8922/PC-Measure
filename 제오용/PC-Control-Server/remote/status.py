import os
from fastapi import HTTPException
from .client import request
from . import resolver
from plugins.discord.client import setting

def status():
    try:
        result=request('/system/status',{},'GET')
        endpoint=resolver.last_known() or {}
        return dict(connected=True,pc_code=setting('REMOTE_PC_CODE') or '0001',base_url=result['base_url'],source='discord',last_updated=endpoint.get('last_updated'),server_status=result.get('response'))
    except HTTPException as exc:
        return dict(connected=False,reason=str(exc.detail),last_known_url=(resolver.last_known() or {}).get('base_url'),source='discord')
