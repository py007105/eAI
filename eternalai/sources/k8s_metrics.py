"""Kubernetes Prometheus signals with the same columns as Docker telemetry."""
from __future__ import annotations

import os
import re
import time

import httpx
import numpy as np
import pandas as pd

from .. import config
from ..collector import Prom, Q

_NAME = re.compile(r"^[a-z0-9](?:[-a-z0-9]*[a-z0-9])?$")

QUERIES = {
    "cpu_cores": 'sum(rate(container_cpu_usage_seconds_total{{namespace="{ns}",pod=~"{s}-.*",container!=""}}[30s]))',
    "mem_bytes": 'sum(container_memory_working_set_bytes{{namespace="{ns}",pod=~"{s}-.*",container!=""}})',
    "mem_limit_bytes": 'sum(kube_pod_container_resource_limits{{namespace="{ns}",pod=~"{s}-.*",resource="memory"}})',
    "up": 'min(kube_pod_status_ready{{namespace="{ns}",pod=~"{s}-.*",condition="true"}})',
    "restarts_3m": 'sum(increase(kube_pod_container_status_restarts_total{{namespace="{ns}",pod=~"{s}-.*"}}[3m]))',
    "deploys_3m": 'changes(kube_deployment_status_observed_generation{{namespace="{ns}",deployment="{s}"}}[3m])',
}
UNOBSERVED = tuple(k for k in Q if k not in QUERIES)


class KubernetesProm(Prom):
    def __init__(self, url: str, namespace: str, token: str | None = None,
                 client: httpx.Client | None = None):
        if not _NAME.fullmatch(namespace):
            raise ValueError("invalid Kubernetes namespace")
        self.namespace = namespace
        headers = {"Authorization": f"Bearer {token}"} if token else None
        self.c = client or httpx.Client(base_url=url, timeout=10, headers=headers)
        self.failures = []
        self._down_until = 0.0

    @classmethod
    def from_env(cls, namespace: str):
        return cls(os.getenv("PROMETHEUS_URL", config.PROMETHEUS_URL), namespace,
                   os.getenv("PROMETHEUS_TOKEN") or None)

    def signals(self, service: str, seconds: int = 180, end: float | None = None) -> pd.DataFrame:
        if not _NAME.fullmatch(service):
            raise ValueError("invalid Kubernetes Deployment name")
        end = end or time.time()
        start = end - seconds
        grid = np.arange(int(start) // config.STEP_S * config.STEP_S, int(end), config.STEP_S, dtype=float)
        columns = {name: pd.Series(np.nan, index=grid) for name in Q}
        failed = []
        for name, template in QUERIES.items():
            series, ok = self._range(template.format(ns=self.namespace, s=service), start, end)
            if not ok:
                failed.append(name)
            elif len(series):
                columns[name] = series.reindex(grid, method="nearest", tolerance=config.STEP_S)
        frame = pd.DataFrame(columns, index=grid)
        frame.attrs["failed_queries"] = sorted(failed)
        frame.attrs["unobserved_queries"] = list(UNOBSERVED)
        return frame

    def oom_killed(self, service: str) -> float:
        if not _NAME.fullmatch(service):
            raise ValueError("invalid Kubernetes Deployment name")
        query = ('max(kube_pod_container_status_last_terminated_reason'
                 f'{{namespace="{self.namespace}",pod=~"{service}-.*",reason="OOMKilled"}})')
        return self.instant(query)
