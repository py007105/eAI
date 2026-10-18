"""Memory guard for long unattended runs (tooling). Waits, and logs, instead of starting work when free RAM is low.

Two memory kills stopped runs on this machine (the forecast check and the surge capture): the host had about 1.2 GB free and the tool that supervises background
commands stopped them. A run started under that pressure is lost work, so every runner calls `wait_for_memory` before it starts a run.

    python scripts/memguard.py            # print free RAM once
"""
from __future__ import annotations

import ctypes
import sys
import time


def free_ram_gb() -> float:
    """Physical memory available to start work, in GB (Windows: GlobalMemoryStatusEx; Linux: MemAvailable)."""
    if sys.platform == "win32":
        class MEMSTAT(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong), ("ullTotalPhys", ctypes.c_ulonglong),
                        ("ullAvailPhys", ctypes.c_ulonglong), ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong), ("sullAvailExtendedVirtual", ctypes.c_ulonglong)]
        s = MEMSTAT()
        s.dwLength = ctypes.sizeof(MEMSTAT)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(s))
        return s.ullAvailPhys / 1e9
    with open("/proc/meminfo") as f:
        for line in f:
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) * 1024 / 1e9
    raise RuntimeError("cannot read free memory on this platform")


def wait_for_memory(min_free_gb: float, poll_s: float = 20.0, max_wait_s: float = 3600.0, log=print, sleep=time.sleep, free=free_ram_gb) -> float:
    """Return the seconds waited once free RAM is at least `min_free_gb`; raise TimeoutError after `max_wait_s`. Logs once per minute while waiting."""
    if min_free_gb <= 0:
        return 0.0
    waited, last_log = 0.0, -60.0
    while True:
        f = free()
        if f >= min_free_gb:
            if waited:
                log(f"MEMGUARD: free RAM {f:.2f} GB >= {min_free_gb:.2f} GB after waiting {waited:.0f} s; continuing", flush=True)
            return waited
        if waited - last_log >= 60:
            log(f"MEMGUARD: free RAM {f:.2f} GB < {min_free_gb:.2f} GB; waiting (not starting a run)", flush=True)
            last_log = waited
        if waited >= max_wait_s:
            raise TimeoutError(f"free RAM stayed below {min_free_gb:.2f} GB for {max_wait_s:.0f} s")
        sleep(poll_s)
        waited += poll_s


if __name__ == "__main__":
    print(f"free RAM: {free_ram_gb():.2f} GB")
