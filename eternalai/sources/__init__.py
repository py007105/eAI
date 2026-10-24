"""Runtime-specific observations for the EternalAI engine."""
from __future__ import annotations

import os

from .. import config, rulebook
from ..collector import DockerView, Prom
from .k8s_metrics import KubernetesProm
from .k8s_state import KubernetesView


def make_sources(env=None, apps=None, core=None, prom_client=None):
    env = os.environ if env is None else env
    source = env.get("METRICS_SOURCE", env.get("RUNTIME", "docker")).strip().lower()
    if source == "docker":
        return Prom(), DockerView()
    if source != "kubernetes":
        raise ValueError("METRICS_SOURCE must be docker or kubernetes")
    namespace = env.get("KUBERNETES_NAMESPACE", "").strip()
    if not namespace or namespace not in rulebook.load().namespaces:
        raise PermissionError("telemetry namespace is not allowed by the rulebook")
    # KUBERNETES_METRICS chooses the Prometheus queries:
    # - "cluster" (default): cAdvisor + kube-state-metrics (KubernetesProm), for workloads without our /metrics;
    # - "app": our own shop's /metrics, scraped with the Compose labels (deploy/kind/shop/prometheus.yaml), read with the
    #   unchanged Docker queries (collector.Prom), so the trained models see the same columns as under Compose.
    profile = env.get("KUBERNETES_METRICS", "cluster").strip().lower()
    if profile == "app":
        if env.get("PROMETHEUS_TOKEN"):
            raise ValueError("KUBERNETES_METRICS=app does not send PROMETHEUS_TOKEN; use the cluster profile")
        return Prom(env.get("PROMETHEUS_URL", config.PROMETHEUS_URL)), KubernetesView(namespace, apps=apps, core=core)
    if profile != "cluster":
        raise ValueError("KUBERNETES_METRICS must be cluster or app")
    return (KubernetesProm(env.get("PROMETHEUS_URL", config.PROMETHEUS_URL), namespace,
                           env.get("PROMETHEUS_TOKEN") or None, client=prom_client),
            KubernetesView(namespace, apps=apps, core=core))
