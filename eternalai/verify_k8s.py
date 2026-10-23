"""Kubernetes recovery verification: target, callers and frontend must stay healthy."""
from __future__ import annotations

import os
import time

import httpx

from . import config
from .sources.service_map import callers


def probe_once(service: str, topology: dict[str, list[str]], namespace: str,
               apps, client: httpx.Client, frontend_url: str) -> tuple[bool, float, str]:
    began = time.perf_counter()
    try:
        for name in [service, *callers(topology).get(service, [])]:
            deployment = apps.read_namespaced_deployment(name, namespace)
            desired = deployment.spec.replicas or 0
            ready = deployment.status.ready_replicas or 0
            if desired < 1 or ready != desired:
                return False, time.perf_counter() - began, f"{name} has {ready}/{desired} Ready"
        response = client.get(frontend_url.rstrip("/") + "/", timeout=5)
        return response.status_code == 200, time.perf_counter() - began, f"HTTP {response.status_code}"
    except Exception as exc:  # API and HTTP failures count as failed observations, not successful recovery
        return False, time.perf_counter() - began, type(exc).__name__


def verify_recovery_k8s(service: str, topology: dict[str, list[str]], namespace: str,
                        observation_s: float = config.OBSERVATION_S, interval_s: float = 1.0,
                        frontend_url: str | None = None, apps=None, client: httpx.Client | None = None) -> dict:
    if apps is None:
        from kubernetes import client as kube_client, config as kube_config
        kube_config.load_incluster_config()
        apps = kube_client.AppsV1Api()
    url = frontend_url or os.getenv("KUBERNETES_FRONTEND_URL", f"http://frontend.{namespace}.svc.cluster.local")
    own_client = client is None
    client = client or httpx.Client()
    probes = []
    try:
        deadline = time.monotonic() + observation_s
        while time.monotonic() < deadline:
            probes.append(probe_once(service, topology, namespace, apps, client, url))
            time.sleep(interval_s)
    finally:
        if own_client:
            client.close()
    good = sum(ok for ok, _duration, _detail in probes)
    rate = good / len(probes) if probes else 0.0
    outcome = "recovered" if rate == 1.0 else ("partially_recovered" if rate >= 0.5 else "unresolved")
    return {"outcome": outcome, "probes": len(probes), "success_rate": round(rate, 3),
            "p_max_latency_s": round(max((duration for _ok, duration, _detail in probes), default=0), 3),
            "last_detail": probes[-1][2] if probes else "no probes"}
