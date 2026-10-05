import config
import time

def run(**kw):
    import config
    return {'server': 'running', 'uptime': time.monotonic() - config.started, 'stopped': config.stop_event.is_set()}
