"""Environment header for results files: package versions, hardware, and the data hash (when given)."""
import hashlib
import os
import platform
from pathlib import Path


def data_hash(runs_dir, exclude=()) -> str:
    """sha256 over every run's truth and signal files (sorted by name), excluding the given run ids."""
    h = hashlib.sha256()
    for p in sorted(Path(runs_dir).glob("*.json")):
        if p.stem in exclude or p.name == "EXCLUDED.json":
            continue
        for f in (p, p.with_suffix(".csv")):
            h.update(f.name.encode())
            h.update(f.read_bytes())
    return h.hexdigest()


def ram_gb() -> float:
    try:
        import ctypes

        class MS(ctypes.Structure):
            _fields_ = [("l", ctypes.c_ulong), ("m", ctypes.c_ulong), ("tp", ctypes.c_ulonglong), ("ap", ctypes.c_ulonglong),
                        ("tpf", ctypes.c_ulonglong), ("apf", ctypes.c_ulonglong), ("tv", ctypes.c_ulonglong),
                        ("av", ctypes.c_ulonglong), ("ae", ctypes.c_ulonglong)]
        s = MS()
        s.l = ctypes.sizeof(MS)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(s))
        return round(s.tp / 1e9, 1)
    except Exception:
        return float("nan")


def env_lines(seeds: str = "", runs_dir=None, exclude=()) -> list[str]:
    import numpy
    import pandas
    import sklearn
    import scipy
    out = [f"- environment: Python {platform.python_version()}, numpy {numpy.__version__}, pandas {pandas.__version__}, "
           f"scikit-learn {sklearn.__version__}, scipy {scipy.__version__}",
           f"- hardware: {platform.processor() or platform.machine()}, {os.cpu_count()} logical CPUs, {ram_gb()} GB RAM, "
           f"{platform.platform()}"]
    if seeds:
        out.append(f"- seeds: {seeds}")
    if runs_dir:
        out.append(f"- data hash (sha256 of retained run files): `{data_hash(runs_dir, exclude)}`")
    return out
