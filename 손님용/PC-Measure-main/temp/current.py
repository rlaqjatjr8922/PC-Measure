import config

def run():
    path = config.DATA_DIR / 'tmp'
    path.mkdir(parents=True, exist_ok=True)
    return {'path': str(path), 'alias': 'temp:/'}
