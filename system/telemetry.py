import config
import time

def run():
    import psutil
    with config.lock:
        counts = dict(config.stats)
    return {**counts, 'uptime': time.monotonic() - config.started,
            'cpu_percent': psutil.cpu_percent(), 'memory': dict(psutil.virtual_memory()._asdict())}
