import ctypes
from ctypes import wintypes
import json
from pathlib import Path
import subprocess
import sys
import time
import urllib.request


class BasicLimits(ctypes.Structure):
    _fields_ = [
        ('process_time', ctypes.c_int64), ('job_time', ctypes.c_int64),
        ('flags', wintypes.DWORD), ('min_ws', ctypes.c_size_t),
        ('max_ws', ctypes.c_size_t), ('active', wintypes.DWORD),
        ('affinity', ctypes.c_size_t), ('priority', wintypes.DWORD),
        ('scheduling', wintypes.DWORD),
    ]


class ExtendedLimits(ctypes.Structure):
    _fields_ = [
        ('basic', BasicLimits), ('io', ctypes.c_uint64 * 6),
        ('process_memory', ctypes.c_size_t), ('job_memory', ctypes.c_size_t),
        ('peak_process', ctypes.c_size_t), ('peak_job', ctypes.c_size_t),
    ]


def protect_process_tree():
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    kernel.CreateJobObjectW.restype = wintypes.HANDLE
    kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    kernel.SetInformationJobObject.restype = wintypes.BOOL
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel.AssignProcessToJobObject.restype = wintypes.BOOL
    job = kernel.CreateJobObjectW(None, None)
    if not job:
        raise ctypes.WinError(ctypes.get_last_error())
    limits = ExtendedLimits()
    limits.basic.flags = 0x2000  # Kill the entire job when its sole handle closes.
    if not kernel.SetInformationJobObject(job, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
        raise ctypes.WinError(ctypes.get_last_error())
    if not kernel.AssignProcessToJobObject(job, kernel.GetCurrentProcess()):
        raise ctypes.WinError(ctypes.get_last_error())
    # The supervisor owns the handle. Children inherit job membership, not this handle.
    # Windows closes it even if the console or supervisor is forcibly terminated.
    return job


def monitor(processes):
    while True:
        for name, process in processes:
            code = process.poll()
            if code is not None:
                print(f'{name} closed ({code}). Closing the whole group.', flush=True)
                return 0 if code == 0 else 1
        time.sleep(0.2)


def main():
    job = protect_process_tree()
    if '--check' in sys.argv:
        print('OK: Windows process-group cleanup is available.', flush=True)
        return 0
    if '--self-test' in sys.argv:
        child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)'])
        trigger = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(1)'])
        print(f'TEST_CHILD={child.pid}', flush=True)
        return monitor([('test child', child), ('test trigger', trigger)])

    folder = Path(__file__).resolve().parent
    control = folder.parent / '\uc81c\uc624\uc6a9'
    guest = folder.parent / '\uc190\ub2d8\uc6a9'
    processes = []
    with (folder / 'server.stdout.log').open('ab') as stdout, (folder / 'server.stderr.log').open('ab') as stderr:
        server = subprocess.Popen(
            [sys.executable, '-B', 'server.py'], cwd=control / 'PC-Control-Server',
            stdout=stdout, stderr=stderr, creationflags=subprocess.CREATE_NO_WINDOW,
        )
        processes.append(('PC Control Server', server))
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if server.poll() is not None:
                raise RuntimeError('Server stopped. See server.stderr.log.')
            try:
                with opener.open('http://127.0.0.1:8002/health', timeout=1) as response:
                    ready = json.load(response).get('server') == 'PC Control Server'
                if ready:
                    break
            except (OSError, ValueError):
                pass
            time.sleep(0.2)
        else:
            raise RuntimeError('Server startup timed out. See server.stderr.log.')
        processes.append(('PC-Measure', subprocess.Popen([str(guest / 'PC-Measure.exe')], cwd=guest)))
        processes.append(('Tunnel', subprocess.Popen([str(control / 'tunnel-client.exe'), 'run', '--profile', 'pc-control'], cwd=control)))
        print('All started. Closing any program or this window closes the whole group.', flush=True)
        return monitor(processes)


if __name__ == '__main__':
    try:
        result = main()
    except KeyboardInterrupt:
        result = 0
    except Exception as error:
        print(f'Launch failed: {error}', file=sys.stderr, flush=True)
        result = 1
    sys.exit(result)
