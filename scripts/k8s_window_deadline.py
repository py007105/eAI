"""Cap scheduled Package A work before the reserved Docker window ends.

The detached runner sets EAI_K8S_WORK_DEADLINE_IST to leave time for cleanup.
Manual runs without that variable retain the documented per-command timeouts.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))
ENV = "EAI_K8S_WORK_DEADLINE_IST"


def remaining_work_seconds() -> float | None:
    raw = os.getenv(ENV)
    if not raw:
        return None
    deadline = datetime.fromisoformat(raw)
    if deadline.tzinfo is None:
        raise ValueError(f"{ENV} must contain a timezone offset")
    return (deadline - datetime.now(IST)).total_seconds()


def bounded_timeout(requested: float, *, cleanup: bool = False) -> float:
    if cleanup:
        return requested
    remaining = remaining_work_seconds()
    if remaining is None:
        return requested
    if remaining <= 1:
        raise TimeoutError("assigned Kubernetes work cutoff reached")
    return min(requested, remaining)
