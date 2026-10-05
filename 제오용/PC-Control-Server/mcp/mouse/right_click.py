from measure_tools import invoke

def run(**parameters):
    return invoke('/mouse/right_click', parameters)
