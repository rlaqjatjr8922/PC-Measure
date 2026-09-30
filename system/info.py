import os
import platform

def run(**kw):
    return {'os': platform.system(), 'release': platform.release(), 'architecture': platform.machine(), 'python': platform.python_version(), 'cpu_count': os.cpu_count()}
