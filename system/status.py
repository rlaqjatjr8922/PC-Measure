from core.system_ops import system

def run(**kwargs):
    return system('status', **kwargs)
