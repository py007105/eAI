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
    return (KubernetesProm(env.get("PROMETHEUS_URL", config.PROMETHEUS_URL), namespace,
                           env.get("PROMETHEUS_TOKEN") or None, client=prom_client),
            KubernetesView(namespace, apps=apps, core=core))
