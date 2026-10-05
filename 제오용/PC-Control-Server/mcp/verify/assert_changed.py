from measure_tools import invoke

def run(**parameters):
    return invoke('/verify/assert_changed', parameters)
