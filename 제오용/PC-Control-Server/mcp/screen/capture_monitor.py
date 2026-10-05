from measure_tools import invoke

def run(**parameters):
    return invoke('/screen/capture_monitor', parameters)
