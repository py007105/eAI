"""Choose a recovery driver without changing the Docker default."""
from __future__ import annotations

import os

from .. import rulebook
from .docker import DockerDriver
from .k8s import KubernetesDriver


def make_driver(env=None, policy=None, apps=None, core=None, audit_path=None):
    env = os.environ if env is None else env
    runtime = env.get("RUNTIME", "docker").strip().lower()
    if runtime == "docker":
        return DockerDriver()
    if runtime != "kubernetes":
        raise ValueError("RUNTIME must be docker or kubernetes")
    policy = policy or rulebook.load()
    allowed = policy.namespaces
    namespace = env.get("KUBERNETES_NAMESPACE", "").strip() or (allowed[0] if allowed else "")
    kwargs = {"audit_path": audit_path} if audit_path is not None else {}
    return KubernetesDriver(namespace, allowed, apps=apps, core=core, **kwargs)
