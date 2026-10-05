from measure_tools import invoke

def run(**parameters):
    return invoke('/mouse/click', parameters)
