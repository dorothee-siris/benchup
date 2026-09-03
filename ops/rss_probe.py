"""ops/rss_probe.py -- stdlib-only (ctypes) Windows RSS reader, for the CURRENT
process or an arbitrary external PID (e.g. a spawned `streamlit run` child).

Written for the RAM-fit gate: `psutil` is not installed
in env-app and must not be added to requirements.txt for a test-only need, so
this copies+extends `test_engine_identity.py::peak_rss_gb`'s own ctypes
PROCESS_MEMORY_COUNTERS pattern (same struct) to accept a `pid`, opening the
target process with PROCESS_QUERY_INFORMATION | PROCESS_VM_READ (0x0400 |
0x0010) -- no admin needed for a process owned by the same user.

Returns MB (not GB, unlike the identity test's own helper) since the ram
budget numbers this stream reports are in the 300-1500 MB range.
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt

PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010


class _PMC(ctypes.Structure):
    _fields_ = [("cb", wt.DWORD), ("PageFaultCount", wt.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]


def process_rss_mb(pid: int | None = None) -> tuple[float, float] | None:
    """(working_set_mb, peak_working_set_mb) for `pid` (current process if
    None), or None if the process cannot be opened (already exited, or a
    permissions edge case) -- callers must treat that as "sample skipped",
    never as zero."""
    psapi = ctypes.windll.psapi
    kernel32 = ctypes.windll.kernel32
    psapi.GetProcessMemoryInfo.argtypes = [wt.HANDLE, ctypes.POINTER(_PMC), wt.DWORD]
    psapi.GetProcessMemoryInfo.restype = wt.BOOL
    handle = None
    try:
        if pid is None:
            handle = kernel32.GetCurrentProcess()
        else:
            handle = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, int(pid))
            if not handle:
                return None
        c = _PMC()
        c.cb = ctypes.sizeof(_PMC)
        if not psapi.GetProcessMemoryInfo(handle, ctypes.byref(c), c.cb):
            return None
        return (c.WorkingSetSize / (1024 ** 2), c.PeakWorkingSetSize / (1024 ** 2))
    except Exception:
        return None
    finally:
        if pid is not None and handle:
            kernel32.CloseHandle(handle)
