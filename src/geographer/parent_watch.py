"""Exit a child service when the process that owns it has gone.

A library's Core starts its Geo service and passes its own pid. If the Core crashes or is
force-killed it can no longer stop the service, so the service watches the parent instead.
On Windows the parent is held by an open handle taken at startup, so its pid cannot be reused
while we wait; elsewhere the pid is polled.
"""
from __future__ import annotations

import os
import sys
import threading
import time
from typing import Callable


def _wait_windows(pid: int, stop: threading.Event) -> bool:
    import ctypes
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    k.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
    k.OpenProcess.restype = ctypes.c_void_p
    k.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    k.WaitForSingleObject.restype = ctypes.c_uint32
    k.CloseHandle.argtypes = [ctypes.c_void_p]
    handle = k.OpenProcess(0x00100000, False, pid)             # SYNCHRONIZE
    if not handle:
        return True                                             # already gone
    try:
        while not stop.is_set():
            if k.WaitForSingleObject(handle, 500) == 0:         # WAIT_OBJECT_0: it exited
                return True
        return False
    finally:
        k.CloseHandle(handle)


def _wait_posix(pid: int, stop: threading.Event) -> bool:
    while not stop.is_set():
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        except PermissionError:
            pass
        time.sleep(0.5)
    return False


def watch_parent(pid: int, on_gone: Callable[[], None]) -> threading.Event:
    """Call `on_gone` once when `pid` exits. Returns an event that cancels the watch."""
    stop = threading.Event()

    def run() -> None:
        gone = _wait_windows(pid, stop) if sys.platform == "win32" else _wait_posix(pid, stop)
        if gone:
            on_gone()

    threading.Thread(target=run, name="parent-watch", daemon=True).start()
    return stop
