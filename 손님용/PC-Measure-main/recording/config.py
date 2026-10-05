from activity import configure
def run(scope='query',screenshot='query'):
    return configure(None if scope=='query' else scope,None if screenshot=='query' else screenshot)
