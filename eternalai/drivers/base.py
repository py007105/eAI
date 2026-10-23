"""The small recovery-driver contract shared by Docker and Kubernetes."""
from __future__ import annotations

from typing import Protocol


class NotSupported(RuntimeError):
    """The selected runtime cannot safely perform this operation."""


UNSUPPORTED = ("pause_rollout", "change_limits", "patch_hpa", "cordon_node", "create_job")


class Driver(Protocol):
    runtime: str
    audit: list[dict]

    def run(self, runbook_id: str, service: str, actor: str,
            evidence_ids: list[str] | None = None, reason: str = "") -> dict: ...

    def log_verification(self, incident_id: str, runbook_id: str, service: str,
                         outcome: str, success_rate: float) -> dict: ...

    def replicas(self, service: str) -> int: ...
    def restart(self, service: str) -> dict: ...
    def scale_to(self, service: str, n: int) -> dict: ...
    def rollback(self, service: str) -> dict: ...
    def cleanup(self, service: str) -> dict: ...
    def delete_pod(self, service: str) -> dict: ...
