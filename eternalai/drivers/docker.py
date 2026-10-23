"""Docker driver: preserve the existing Executor's runbooks and audit trail."""
from __future__ import annotations

from ..executor import Executor
from .base import NotSupported, UNSUPPORTED


class DockerDriver:
    runtime = "docker"

    def __init__(self, executor: Executor | None = None):
        self.executor = executor if executor is not None else Executor()
        self.audit = self.executor.audit

    def run(self, runbook_id, service, actor, evidence_ids=None, reason=""):
        return self.executor.run(runbook_id, service, actor, evidence_ids, reason)

    def log_verification(self, incident_id, runbook_id, service, outcome, success_rate):
        return self.executor.log_verification(incident_id, runbook_id, service, outcome, success_rate)

    def replicas(self, service):
        return 1

    def restart(self, service):
        return self.executor.restart_service(service)

    def rollback(self, service):
        return self.executor.rollback_release(service)

    def cleanup(self, service):
        return self.executor.clear_temp_path(service)

    def _unsupported(self, operation, service):
        self.executor._log(runbook=operation, service=service, actor="driver", reason="unsupported in Docker runtime",
                           ok=False, error="NotSupported", evidence_ids=[])
        raise NotSupported(f"{operation} is not supported in Docker runtime")

    def scale_to(self, service, n):
        return self._unsupported("scale_to", service)

    def delete_pod(self, service):
        return self._unsupported("delete_pod", service)

    def __getattr__(self, name):
        if name in UNSUPPORTED:
            return lambda service, *args, **kwargs: self._unsupported(name, service)
        raise AttributeError(name)
