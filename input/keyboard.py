from core.desktop import keyboard

def run(mode, **kwargs):
    return keyboard('press' if mode == 'key' else mode, **kwargs)
