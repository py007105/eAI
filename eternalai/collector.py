"""Telemetry access: Prometheus time series and Docker container state.

Prometheus gives rates/latency/memory; Docker gives facts Prometheus cannot (is it
running, exit code, OOM-killed, image tag, start time). Missing data stays NaN.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

import docker
import httpx
import numpy as np
import pandas as pd

from . import config

Q = {
    "req_rate": 'sum(rate(http_requests_total{{service="{s}"}}[10s]))',
    "err_rate": 'sum(rate(http_requests_total{{service="{s}",status=~"5.."}}[10s]))',
    "p95_s": 'histogram_quantile(0.95, sum by (le) (rate(http_request_duration_seconds_bucket{{service="{s}"}}[10s])))',
    "mem_bytes": 'app_memory_bytes{{service="{s}"}}',
    "mem_limit_bytes": 'app_memory_limit_bytes{{service="{s}"}}',
    "cpu_cores": 'rate(process_cpu_seconds_total{{instance_name="{s}"}}[10s])',
    "up": 'up{{job="app",instance_name="{s}"}}',
    "dep_fail_rate": 'sum(rate(dependency_calls_total{{service="{s}",outcome="error"}}[10s]))',
    "error_log_rate": 'rate(error_logs_total{{service="{s}"}}[10s])',
    "restarts_3m": 'changes(app_start_time_seconds{{service="{s}"}}[3m])',
    "deploys_3m": 'changes(app_release_seq{{service="{s}"}}[3m])',
    "scratch_bytes": 'app_scratch_disk_bytes{{service="{s}"}}',
}


class Prom:
    def __init__(self, url=config.PROMETHEUS_URL):
        self.c = httpx.Client(base_url=url, timeout=10)

    def instant(self, q: str):
        r = self.c.get("/api/v1/query", params={"query": q}).json()
        res = r["data"]["result"]
        return float(res[0]["value"][1]) if res else np.nan

    def range(self, q: str, start: float, end: float, step=config.STEP_S) -> pd.Series:
        r = self.c.get("/api/v1/query_range", params={"query": q, "start": start, "end": end, "step": step}).json()
        res = r["data"]["result"]
        if not res:
            return pd.Series(dtype=float)
        v = np.array(res[0]["values"], dtype=float)
        return pd.Series(v[:, 1], index=v[:, 0])

    def signals(self, service: str, seconds: int = 180, end: float | None = None) -> pd.DataFrame:
        """Raw signal frame for `service`, indexed by unix seconds on a 2 s grid. NaN where unobserved."""
        end = end or time.time()
        start = end - seconds
        cols = {k: self.range(q.format(s=service), start, end) for k, q in Q.items()}
        # failures of this service's calls to each other service (evidence for blaming the callee)
        for tgt in config.TOPOLOGY.get(service, []):
            cols[f"depfail_{tgt}"] = self.range(
                f'sum(rate(dependency_calls_total{{service="{service}",target="{tgt}",outcome="error"}}[10s]))',
                start, end)
        grid = np.arange(int(start) // config.STEP_S * config.STEP_S, int(end), config.STEP_S, dtype=float)
        df = pd.DataFrame({k: v.reindex(grid, method="nearest", tolerance=config.STEP_S) if len(v) else np.nan
                           for k, v in cols.items()}, index=grid)
        # a service that returns no rate series because it received no traffic has an observed rate of 0 only
        # if it was up; if it was not scraped (up NaN/0) the rate stays NaN.
        up = df["up"].fillna(0) > 0
        for c in ["req_rate", "err_rate", "dep_fail_rate", "error_log_rate"] + [c for c in df if c.startswith("depfail_")]:
            df[c] = df[c].where(~(df[c].isna() & up), 0.0)
        return df


@dataclass
class ContainerState:
    service: str
    running: bool
    status: str
    exit_code: int | None
    oom_killed: bool
    image_tag: str
    release_seq: int
    started_at: float
    container_id: str


@dataclass
class DockerView:
    """Reads container state and tracks deploy / restart events observed over time."""
    client: docker.DockerClient = field(default_factory=docker.from_env)
    last: dict = field(default_factory=dict)
    events: list = field(default_factory=list)  # {"t","service","kind","detail"}

    def containers(self) -> dict[str, docker.models.containers.Container]:
        out = {}
        for c in self.client.containers.list(all=True, filters={"label": "eai.managed=true"}):
            out[c.labels.get("com.docker.compose.service", c.name)] = c
        return out

    def state(self) -> dict[str, ContainerState]:
        out = {}
        for svc, c in self.containers().items():
            c.reload()
            s = c.attrs["State"]
            tag = c.attrs["Config"]["Image"].split(":")[-1]  # reference it was created from
            seq = int(c.image.labels.get("eai.release_seq", 0))
            started = pd.Timestamp(s["StartedAt"]).timestamp() if s.get("StartedAt") else float("nan")
            out[svc] = ContainerState(svc, bool(s["Running"]), s["Status"], s.get("ExitCode"),
                                      bool(s.get("OOMKilled")), tag, seq, started, c.id)
        return out

    def poll(self) -> dict[str, ContainerState]:
        """Record observed changes (restart, new image tag, stop) since the previous poll."""
        now, cur = time.time(), self.state()
        for svc, st in cur.items():
            p = self.last.get(svc)
            if p:
                if st.image_tag != p.image_tag:
                    self.events.append({"t": now, "service": svc, "kind": "deploy",
                                        "detail": f"{p.image_tag} -> {st.image_tag}"})
                elif st.started_at != p.started_at and st.running:
                    self.events.append({"t": now, "service": svc, "kind": "restart", "detail": "container restarted"})
                if p.running and not st.running:
                    self.events.append({"t": now, "service": svc, "kind": "stopped",
                                        "detail": f"exit={st.exit_code} oom={st.oom_killed}"})
        self.last = cur
        return cur

    def deploy_age_s(self, service: str, now: float | None = None) -> float:
        """Seconds since the last observed deploy of `service`; NaN if none observed (never invented)."""
        now = now or time.time()
        ts = [e["t"] for e in self.events if e["service"] == service and e["kind"] == "deploy"]
        return now - max(ts) if ts else float("nan")

    def logs(self, service: str, tail: int = 50) -> list[str]:
        c = self.containers().get(service)
        return c.logs(tail=tail).decode(errors="replace").splitlines() if c else []
