from core import desktop

def run(mode, **kwargs):
    if mode == 'position':
        return desktop.mouse(mode)
    if mode == 'scroll':
        return desktop.mouse(mode, **kwargs)
    options = {k:kwargs.pop(k) for k in ('button','clicks','interval','duration') if k in kwargs}
    if mode == 'click':
        kwargs.update(desktop.mouse('position'))
    if mode == 'drag':
        start=desktop.mouse('position')
        kwargs={'start_x':start['x'],'start_y':start['y'],'end_x':kwargs['x'],'end_y':kwargs['y']}
    return desktop.mouse(mode,options=options,**kwargs)
