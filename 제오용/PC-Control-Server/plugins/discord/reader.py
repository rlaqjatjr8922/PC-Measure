from .client import messages
from .parser import parse

def latest(code):
    before=None
    for _ in range(10):
        batch=messages(before)
        for message in sorted(batch,key=lambda m:int(m.get('id','0')),reverse=True):
            url=parse(message.get('content'),code)
            if url: return url
        if len(batch)<100: break
        before=min((m['id'] for m in batch),key=int)
    raise RuntimeError('최근 1000개 메시지에서 '+code+' 주소를 찾지 못했습니다.')
