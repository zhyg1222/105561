from __future__ import annotations

import sys
from typing import Any


def acquire_named_mutex(name: str) -> Any | None:
    if sys.platform != "win32":
        return object()
    import ctypes

    kernel32 = ctypes.windll.kernel32
    handle = kernel32.CreateMutexW(None, False, str(name))
    if not handle:
        return None
    if kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        kernel32.CloseHandle(handle)
        return None
    return handle


def release_named_mutex(handle: Any | None) -> None:
    if sys.platform == "win32" and handle is not None:
        import ctypes

        ctypes.windll.kernel32.CloseHandle(handle)