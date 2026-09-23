from core.missions import history

def run(**kwargs):
    return history('select', **kwargs)
