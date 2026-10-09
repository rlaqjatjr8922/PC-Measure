from measure_tools import invoke


def run(command, timeout=60):
    return invoke('/system/powershell', {
        'command': command, 'privilege': 'normal', 'timeout': timeout,
    })
