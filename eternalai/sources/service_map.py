"""Discover a call graph from allowed Deployment annotations."""
from __future__ import annotations

from .. import config

ANNOTATION = "eternalai.io/depends-on"


def discover_topology(apps, namespaces, fallback=None) -> tuple[dict[str, list[str]], bool]:
    """Return (topology, used_fallback). Empty or failed discovery is explicit."""
    fallback = config.TOPOLOGY if fallback is None else fallback
    try:
        deployments = []
        for namespace in namespaces:
            deployments.extend(apps.list_namespaced_deployment(namespace).items)
        if not deployments:
            return dict(fallback), True
        names = [item.metadata.name for item in deployments]
        if len(names) != len(set(names)):
            # Bare service names are ambiguous across namespaces in this minimal engine.
            return dict(fallback), True
        graph = {}
        for item in deployments:
            raw = (item.metadata.annotations or {}).get(ANNOTATION, "")
            graph[item.metadata.name] = list(dict.fromkeys(
                name.strip() for name in raw.split(",") if name.strip()))
        return graph, False
    except Exception:
        return dict(fallback), True


def callers(topology: dict[str, list[str]]) -> dict[str, list[str]]:
    return {service: [caller for caller, callees in topology.items() if service in callees]
            for service in topology}
