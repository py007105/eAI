"""Namespaced Kubernetes recovery operations using the official Python client.

The driver has no Secret API and never removes a Deployment, Namespace or PVC.
"""
from __future__ import annotations

import copy
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from .base import NotSupported, UNSUPPORTED

AUDIT_PATH = Path("runtime/audit.jsonl")
_NAME = re.compile(r"^[a-z0-9](?:[-a-z0-9]*[a-z0-9])?$")


class KubernetesDriver:
    runtime = "kubernetes"

    def __init__(self, namespace: str, allowed_namespaces, apps=None, core=None,
                 audit_path: Path = AUDIT_PATH):
        self.allowed_namespaces = frozenset(allowed_namespaces)
        if not self.allowed_namespaces or namespace not in self.allowed_namespaces:
            raise PermissionError("namespace is not allowed by the rulebook")
        self.namespace = namespace
        self.audit_path = Path(audit_path)
        self.audit_path.parent.mkdir(parents=True, exist_ok=True)
        self.audit: list[dict] = []
        if apps is None or core is None:
            from kubernetes import client, config  # official client; injected fake APIs are used only by tests
            config.load_incluster_config()
            apps = apps or client.AppsV1Api()
            core = core or client.CoreV1Api()
        self.apps, self.core = apps, core

    def _target(self, service):
        parts = service.split("/", 1)
        namespace, name = parts if len(parts) == 2 else (self.namespace, service)
        if namespace not in self.allowed_namespaces:
            raise PermissionError("namespace is not allowed by the rulebook")
        if not _NAME.fullmatch(name):
            raise ValueError("invalid Deployment name")
        return namespace, name

    def _log(self, operation, service, actor, reason, ok, result=None, error=None, evidence_ids=None):
        record = {"t": time.time(), "runtime": self.runtime, "runbook": operation,
                  "service": service, "actor": actor, "reason": reason, "ok": ok,
                  "evidence_ids": evidence_ids or []}
        if ok:
            record["result"] = result
        else:
            record["error"] = error
        self.audit.append(record)
        with self.audit_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record) + "\n")
        return record

    def _perform(self, operation, service, fn, actor="driver", reason="", evidence_ids=None):
        try:
            namespace, name = self._target(service)
            result = fn(namespace, name)
        except Exception as exc:
            self._log(operation, service, actor, reason, False, error=type(exc).__name__, evidence_ids=evidence_ids)
            raise
        self._log(operation, service, actor, reason, True, result=result, evidence_ids=evidence_ids)
        return {"ok": True, **result}

    def _restart(self, namespace, name):
        stamp = datetime.now(timezone.utc).isoformat()
        self.apps.patch_namespaced_deployment(
            name, namespace,
            {"spec": {"template": {"metadata": {"annotations": {
                "kubectl.kubernetes.io/restartedAt": stamp}}}}})
        return {"restarted": name, "namespace": namespace, "at": stamp}

    def restart(self, service):
        return self._perform("restart_service", service, self._restart)

    def _replicas(self, namespace, name):
        deployment = self.apps.read_namespaced_deployment(name, namespace)
        return {"replicas": deployment.spec.replicas or 0}

    def replicas(self, service):
        return self._perform("replicas", service, self._replicas)["replicas"]

    def scale_to(self, service, n):
        return self._perform("scale_to", service, lambda ns, name: self._scale(ns, name, n))

    def _scale(self, namespace, name, n):
        if not isinstance(n, int) or isinstance(n, bool) or n < 0:
            raise ValueError("replicas must be a non-negative integer")
        self.apps.patch_namespaced_deployment_scale(name, namespace, {"spec": {"replicas": n}})
        return {"scaled": name, "namespace": namespace, "replicas": n}

    def _delete_pod(self, namespace, name):
        deployment = self.apps.read_namespaced_deployment(name, namespace)
        selector = deployment.spec.selector.match_labels
        if not selector:
            raise ValueError("Deployment has no matchLabels selector")
        label_selector = ",".join(f"{k}={v}" for k, v in sorted(selector.items()))
        replicasets = self.apps.list_namespaced_replica_set(namespace, label_selector=label_selector).items
        owned_rs = {rs.metadata.uid for rs in replicasets
                    if any(ref.kind == "Deployment" and ref.uid == deployment.metadata.uid
                           for ref in (rs.metadata.owner_references or []))}
        pods = self.core.list_namespaced_pod(namespace, label_selector=label_selector).items
        matches = [pod for pod in pods
                   if any(ref.kind == "ReplicaSet" and ref.uid in owned_rs
                          for ref in (pod.metadata.owner_references or []))]
        if not matches:
            raise ValueError("Deployment has no matching Pod")
        pod = matches[0]
        self.core.delete_namespaced_pod(pod.metadata.name, namespace)
        return {"deleted_pod": pod.metadata.name, "deployment": name, "namespace": namespace}

    def delete_pod(self, service):
        return self._perform("delete_pod", service, self._delete_pod)

    def _rollback(self, namespace, name):
        deployment = self.apps.read_namespaced_deployment(name, namespace)
        revision = int(deployment.metadata.annotations["deployment.kubernetes.io/revision"])
        selector = deployment.spec.selector.match_labels
        label_selector = ",".join(f"{k}={v}" for k, v in sorted(selector.items()))
        replicasets = self.apps.list_namespaced_replica_set(namespace, label_selector=label_selector).items
        previous = []
        for rs in replicasets:
            owners = getattr(rs.metadata, "owner_references", []) or []
            if not any(ref.kind == "Deployment" and ref.uid == deployment.metadata.uid for ref in owners):
                continue
            rev = int((rs.metadata.annotations or {}).get("deployment.kubernetes.io/revision", "0"))
            if rev < revision:
                previous.append((rev, rs))
        if not previous:
            raise ValueError("no previous ReplicaSet revision")
        prior_revision, prior_rs = max(previous, key=lambda pair: pair[0])
        template = copy.deepcopy(prior_rs.spec.template)
        (template.metadata.labels or {}).pop("pod-template-hash", None)
        self.apps.patch_namespaced_deployment(name, namespace, {"spec": {"template": template}})
        return {"rolled_back": name, "namespace": namespace, "to_revision": prior_revision}

    def rollback(self, service):
        return self._perform("rollback_release", service, self._rollback)

    def cleanup(self, service):
        return self._unsupported("clear_temp_path", service)

    def _unsupported(self, operation, service):
        def fail(_namespace, _name):
            raise NotSupported(f"{operation} is not supported in Kubernetes runtime")
        return self._perform(operation, service, fail)

    def __getattr__(self, name):
        if name in UNSUPPORTED:
            return lambda service, *args, **kwargs: self._unsupported(name, service)
        raise AttributeError(name)

    def run(self, runbook_id, service, actor, evidence_ids=None, reason=""):
        operations = {"restart_service": self._restart, "recreate_container": self._delete_pod,
                      "rollback_release": self._rollback}
        fn = operations.get(runbook_id)
        if fn is None:
            return self._perform(runbook_id, service, lambda ns, name: self._raise_unsupported(runbook_id),
                                 actor, reason, evidence_ids)
        return self._perform(runbook_id, service, fn, actor, reason, evidence_ids)

    @staticmethod
    def _raise_unsupported(operation):
        raise NotSupported(f"{operation} is not supported in Kubernetes runtime")

    def log_verification(self, incident_id, runbook_id, service, outcome, success_rate):
        self._target(service)
        return self._log("verification", service, "verifier", incident_id, True,
                         {"runbook": runbook_id, "outcome": outcome, "success_rate": success_rate})
