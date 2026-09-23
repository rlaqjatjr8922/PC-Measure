from core.desktop import window
from core import runtime as rt

def run(mode, **kwargs):
    if mode in ('list','find'):
        return window(mode,**kwargs)
    title=kwargs.pop('title')
    matches=[w for w in window('find',title=title) if w['title']==title]
    if len(matches)!=1:
        rt.fail('정확히 일치하는 창이 하나여야 합니다.',409)
    item=matches[0]
    if mode in ('move','resize'):
        return window('position',mode='set',hwnd=item['hwnd'], **{k:kwargs.get(k,item[k]) for k in ('x','y','width','height')})
    return window('focus' if mode=='activate' else mode,hwnd=item['hwnd'])
