"""读取整机CPU与内存计数；首次CPU采样和不可读字段保持未知。"""
import ctypes
import os
from pathlib import Path
from threading import Lock

_previous = None
_lock = Lock()


def counters():
    if os.name == 'nt':
        idle, kernel, user = (ctypes.c_ulonglong() for _ in range(3))
        if not ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)):
            return None
        return kernel.value + user.value, idle.value
    values = (Path('/proc/stat').read_text().splitlines()[0]).split()
    ticks = [int(value) for value in values[1:9]]
    return sum(ticks), ticks[3] + ticks[4]


def used_memory():
    if os.name == 'nt':
        class Memory(ctypes.Structure):
            _fields_ = [('length', ctypes.c_ulong), ('load', ctypes.c_ulong)] + [(name, ctypes.c_ulonglong) for name in
                ('total', 'available', 'page_total', 'page_available', 'virtual_total', 'virtual_available', 'extended')]
        value = Memory(); value.length = ctypes.sizeof(value)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(value)):
            return (value.total - value.available) // 1048576
        return None
    fields = {line.split(':')[0]: int(line.split()[1]) for line in Path('/proc/meminfo').read_text().splitlines() if ':' in line}
    return (fields['MemTotal'] - fields['MemAvailable']) // 1024


def sample():
    global _previous
    utilization, memory = None, None
    with _lock:
        try:
            current = counters()
            if current and _previous:
                total, idle = current[0] - _previous[0], current[1] - _previous[1]
                if total > 0 and 0 <= idle <= total:
                    utilization = round(100 * (total - idle) / total, 2)
            _previous = current
        except (OSError, ValueError, IndexError):
            _previous = None
        try:
            memory = used_memory()
        except (OSError, ValueError, KeyError):
            pass
    return utilization, memory
