from core.macros import run as handle

def run(**kwargs):
    return handle('replay_with_verify', **kwargs)
