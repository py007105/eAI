"""Load RCAEval RE1 cases into the harmonised per-service signal schema.

Layout: <root>/RE1-<OB|SS|TT>/<service>_<fault>/<rep>/{data.csv, inject_time.txt}.
The three systems expose different metrics (OB: cpu/mem/load/latency per service;
SS/TT: cAdvisor + istio). Each service is mapped to the signals EternalAI's live
pipeline uses; what a system lacks stays NaN (never zero-filled):

  cpu_cores (rate, units differ per system; only ratios are used downstream),
  mem_bytes, mem_limit_bytes, p95_s (latency), req_rate, err_rate.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

SYSTEMS = {"OB": "online_boutique", "SS": "sock_shop", "TT": "train_ticket"}
STEP_S = 2  # resample to the 2 s scrape interval used by the live system


@dataclass
class Case:
    case_id: str
    system: str
    root_service: str
    fault: str
    rep: int
    inject_time: int
    signals: dict  # service -> DataFrame indexed by seconds since case start (STEP_S grid)


RATE_LAG_S = 30  # cAdvisor/istio counters update in steps; a short diff is mostly zero


def _rate(s: pd.Series) -> pd.Series:
    r = s.diff(RATE_LAG_S) / RATE_LAG_S  # raw data is 1 s per row
    return r.where(r >= 0)  # counter resets become NaN, not zero


def _service_frames(df: pd.DataFrame, system: str) -> dict:
    t = df["time"].astype(float).values
    t = t - t[0]
    cols = [c for c in df.columns if c != "time"]
    out = {}
    services = sorted({c.split("_")[0] for c in cols})
    for svc in services:
        g = lambda suffix: df[f"{svc}_{suffix}"].astype(float) if f"{svc}_{suffix}" in df else None
        sig = {}
        if system == "OB":
            sig = {"cpu_cores": g("cpu"), "mem_bytes": g("mem"), "p95_s": g("latency"),
                   "req_rate": g("load"), "err_rate": g("error")}
        else:
            cpu = g("container-cpu-usage-seconds-total")
            req = g("istio-request-total")
            err = g("istio-error-total")
            lim = g("container-spec-memory-limit-bytes")
            sig = {"cpu_cores": _rate(cpu) if cpu is not None else None,
                   "mem_bytes": g("container-memory-working-set-bytes"),
                   "mem_limit_bytes": lim.where((lim > 0) & (lim < 1e12)) if lim is not None else None,
                   "p95_s": g("istio-latency-95"),
                   "req_rate": _rate(req) if req is not None else None,
                   "err_rate": _rate(err) if err is not None else None}
        sig = {k: v for k, v in sig.items() if v is not None}
        if not ({"cpu_cores", "mem_bytes", "p95_s"} & sig.keys()):
            continue  # not an application service (node exporters, gateways, ...)
        d = pd.DataFrame(sig)
        d.index = t
        d = d.groupby((d.index // STEP_S) * STEP_S).mean()
        for c in ["cpu_cores", "mem_bytes", "mem_limit_bytes", "p95_s", "req_rate", "err_rate"]:
            if c not in d:
                d[c] = np.nan
        d["up"] = np.nan  # RE1 has no explicit up signal; not invented
        out[svc] = d
    return out


def iter_cases(root: str | Path, systems=("OB", "SS", "TT")):
    root = Path(root)
    for sysk in systems:
        base = root / f"RE1-{sysk}"
        for cdir in sorted(p for p in base.iterdir() if p.is_dir()):
            service, fault = cdir.name.rsplit("_", 1)
            for rep_dir in sorted(p for p in cdir.iterdir() if p.is_dir()):
                df = pd.read_csv(rep_dir / "data.csv")
                inj = int((rep_dir / "inject_time.txt").read_text().strip())
                frames = _service_frames(df, sysk)
                inj_rel = inj - float(df["time"].iloc[0])
                yield Case(f"re1-{sysk.lower()}-{service}-{fault}-{rep_dir.name}", SYSTEMS[sysk],
                           service, fault, int(rep_dir.name), int(inj_rel), frames)
