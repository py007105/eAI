"""Read-only Deployment and Pod state for the engine's container-state interface."""
from __future__ import annotations

import time

import pandas as pd

from ..collector import ContainerState


class KubernetesView:
    def __init__(self, namespace: str, apps=None, core=None):
        if apps is None or core is None:
            from kubernetes import client, config
            config.load_incluster_config()
            apps = apps or client.AppsV1Api()
            core = core or client.CoreV1Api()
        self.apps, self.core = apps, core
        self.namespace = namespace
        self.last: dict[str, ContainerState] = {}
        self.events: list[dict] = []

    def state(self) -> dict[str, ContainerState]:
        out = {}
        for deployment in self.apps.list_namespaced_deployment(self.namespace).items:
            name = deployment.metadata.name
            selector = deployment.spec.selector.match_labels or {}
            if not selector:
                continue
            label_selector = ",".join(f"{key}={value}" for key, value in sorted(selector.items()))
            pods = self.core.list_namespaced_pod(self.namespace, label_selector=label_selector).items
            statuses = [status for pod in pods for status in (pod.status.container_statuses or [])]
            oom = any(getattr(getattr(status.last_state, "terminated", None), "reason", None) == "OOMKilled"
                      for status in statuses)
            spec_replicas = deployment.spec.replicas or 0
            ready = deployment.status.ready_replicas or 0
            image = deployment.spec.template.spec.containers[0].image
            revision = int((deployment.metadata.annotations or {}).get("deployment.kubernetes.io/revision", "0"))
            creation = deployment.metadata.creation_timestamp
            started = pd.Timestamp(creation).timestamp() if creation else float("nan")
            out[name] = ContainerState(
                name, ready == spec_replicas and spec_replicas > 0,
                "Ready" if ready == spec_replicas and spec_replicas > 0 else "NotReady",
                None, oom, image.rsplit(":", 1)[-1], revision, started, deployment.metadata.uid)
        return out

    def poll(self) -> dict[str, ContainerState]:
        current = self.state()
        now = time.time()
        for name, state in current.items():
            before = self.last.get(name)
            if before and state.release_seq != before.release_seq:
                self.events.append({"t": now, "service": name, "kind": "deploy",
                                    "detail": f"revision {before.release_seq} -> {state.release_seq}"})
            elif before and state.running != before.running:
                self.events.append({"t": now, "service": name, "kind": "readiness",
                                    "detail": state.status})
        self.last = current
        return current

    def deploy_age_s(self, service: str, now: float | None = None) -> float:
        events = [event["t"] for event in self.events
                  if event["service"] == service and event["kind"] == "deploy"]
        return (now or time.time()) - max(events) if events else float("nan")

    def logs(self, service: str, tail: int = 50) -> list[str]:
        # Minimal RBAC intentionally has no pods/log permission.
        return []
