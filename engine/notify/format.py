"""Plain-English incident messages shared by notification channels.

The formatter accepts an Incident or its public dictionary. It uses only
structured incident fields, never raw logs or anomaly scores.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from engine.redact import redact


SIGNAL_WORDS = {
    "lat_ratio": "response time is higher than normal",
    "error_ratio": "request errors are higher than normal",
    "cpu_per_req_ratio": "CPU use per request is higher than normal",
    "mem_share": "memory use is higher than normal",
    "mem_rel_growth": "memory is growing faster than normal",
    "mem_slope_share_per_min": "memory is rising steadily",
    "up_frac": "service availability changed",
    "dep_fail_rate": "dependency calls are failing",
    "error_log_rate": "application errors are rising",
    "deploys_3m": "a recent deployment was detected",
    "restarts_in_window": "the service restarted recently",
}


def _field(incident: Any, name: str, default: Any = None) -> Any:
    return incident.get(name, default) if isinstance(incident, dict) else getattr(incident, name, default)


def format_incident(incident: Any, *, show_probability: bool = False) -> str:
    """Format a status update, then redact the entire outgoing message."""
    diagnosis = _field(incident, "diagnosis") or {}
    report = _field(incident, "report") or {}
    actions = _field(incident, "actions") or []
    action = actions[-1] if actions else {}
    services = _field(incident, "services") or []
    ranking = _field(incident, "ranking") or []
    root = diagnosis.get("root") or action.get("service") or (ranking[0].get("service") if ranking else None)
    cause = str(_field(incident, "likely_cause", "unknown") or "unknown").replace("_", " ")
    status = _field(incident, "status", "open")

    lines = [f"Incident {_field(incident, 'id', 'unknown')}: {cause}."]
    confidence = _field(incident, "confidence")
    if show_probability and confidence is not None and not _field(incident, "abstained", False):
        lines.append(f"Confidence: {confidence:.0%}.")

    signals = [SIGNAL_WORDS[s] for s in diagnosis.get("limits_exceeded") or [] if s in SIGNAL_WORDS]
    lines.append("Signals: " + ("; ".join(signals) if signals else "no specific signal recorded") + ".")
    lines.append(f"Likely root: {root or 'not yet identified'}.")
    affected = ", ".join(str(s) for s in services) if services else "not yet identified"
    lines.append(f"Affected services: {affected}.")

    runbook = action.get("runbook_id") or report.get("runbook_id")
    if runbook:
        lines.append(f"Proposed action: {str(runbook).replace('_', ' ')}.")
        lines.append(f"Policy: {str(action.get('verdict') or 'pending').replace('_', ' ')}.")
    else:
        lines.append("Proposed action: none; human review needed.")

    if action.get("approved_by"):
        lines.append(f"Approved by {action['approved_by']}.")

    if status == "recovered" and _field(incident, "verification"):
        closed_t = _field(incident, "closed_t")
        when = datetime.fromtimestamp(closed_t, timezone.utc).strftime("%H:%M:%S UTC") if closed_t else "time unknown"
        lines.append(f"Verified healthy at {when}.")
    elif status == "escalated":
        verdict = str(action.get("verdict") or "")
        if verdict.startswith("rejected_by_"):
            lines.append(f"Rejected by {verdict.removeprefix('rejected_by_').replace('_', ' ')}. Escalated.")
        elif verdict == "expired_unapproved":
            closed_t, proposed_t = _field(incident, "closed_t"), action.get("t")
            elapsed = f" after {round(closed_t - proposed_t)} s" if closed_t is not None and proposed_t is not None else ""
            lines.append(f"Approval expired{elapsed}. Escalated.")
        else:
            lines.append("Escalated for human review.")
    elif status == "awaiting_approval":
        lines.append("Awaiting approval.")
    elif status in ("unresolved", "partially_recovered"):
        lines.append("Recovery was not fully verified. Escalated for human review.")
    else:
        lines.append(f"Status: {str(status).replace('_', ' ')}.")

    lines.append(f"Permanent fix: {report.get('permanent_fix') or 'not yet identified'}.")
    return redact("\n".join(lines))
