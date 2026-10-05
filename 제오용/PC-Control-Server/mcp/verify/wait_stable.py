from measure_tools import invoke

def run(**parameters):
    return invoke('/verify/wait_stable', parameters)
