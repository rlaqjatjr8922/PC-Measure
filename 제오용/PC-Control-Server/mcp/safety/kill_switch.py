from measure_tools import invoke

def run(**parameters):
    return invoke('/safety/kill_switch', parameters)
