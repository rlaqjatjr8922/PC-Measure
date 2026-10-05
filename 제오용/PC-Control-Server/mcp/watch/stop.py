from measure_tools import invoke

def run(**parameters):
    return invoke('/watch/stop', parameters)
