import os
import time
from datetime import datetime,timezone
from threading import RLock
from plugins.discord import reader,cache
from plugins.discord.client import setting

_lock=RLock()
_state=None
_checked=0

def resolve(force=False):
    global _state,_checked
    code=setting('REMOTE_PC_CODE') or '0001'; channel=setting('DISCORD_CHANNEL_ID')
    with _lock:
        if _state is None or (_state['pc_code'],_state['channel_id'])!=(code,channel):
            _state=cache.load(code,channel); _checked=0
        if not force and _state and time.monotonic()-_checked<30: return dict(_state)
        try:
            url=reader.latest(code)
            stamp=_state['last_updated'] if _state and _state['base_url']==url else datetime.now(timezone.utc).isoformat()
            _state=dict(base_url=url,pc_code=code,channel_id=channel,source='discord',last_updated=stamp)
        except RuntimeError:
            _checked=time.monotonic()
            if _state: return dict(_state)
            raise
        _checked=time.monotonic()
        return dict(_state)

def confirmed(endpoint):
    with _lock: cache.save(endpoint)

def last_known():
    return dict(_state) if _state else None
