from measure_tools import invoke

def run(**parameters):
    return invoke('/system/start_app', parameters)
