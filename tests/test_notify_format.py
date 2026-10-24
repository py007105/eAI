"""Telegram message content is useful, calibrated, and safe to send."""
from eternalai.engine import Incident
from eternalai.notify.format import format_incident


def incident():
    inc = Incident(id="incident-1", opened_t=0, status="awaiting_approval",
                   services=["web", "orders"], likely_cause="bad_deploy", confidence=0.86)
    inc.diagnosis = {"root": "orders", "limits_exceeded": ["error_ratio", "deploys_3m"]}
    inc.actions = [{"runbook_id": "rollback_release", "service": "orders", "verdict": "needs_approval"}]
    inc.report = {"runbook_id": "rollback_release", "permanent_fix": "review the release process"}
    return inc


def test_pending_message_has_plan_fields_and_hides_uncalibrated_probability():
    out = format_incident(incident())
    assert out == (
        "Incident incident-1: bad deploy.\n"
        "Signals: request errors are higher than normal; a recent deployment was detected.\n"
        "Likely root: orders.\n"
        "Affected services: web, orders.\n"
        "Proposed action: rollback release.\n"
        "Policy: needs approval.\n"
        "Awaiting approval.\n"
        "Permanent fix: review the release process."
    )
    assert "86%" in format_incident(incident(), show_probability=True)


def test_verified_outcome_and_rejection_are_plain_english():
    inc = incident()
    inc.status, inc.closed_t, inc.verification = "recovered", 0, {"outcome": "recovered"}
    assert "Verified healthy at time unknown." in format_incident(inc)
    inc.closed_t = 1_700_000_000
    inc.actions[-1]["approved_by"] = "alice"
    assert "Approved by alice." in format_incident(inc)
    assert "Verified healthy at 22:13:20 UTC." in format_incident(inc)
    inc.status = "escalated"
    inc.actions[-1]["verdict"] = "rejected_by_alice"
    assert "Rejected by alice. Escalated." in format_incident(inc)
    inc.actions[-1]["approved_by"] = None
    inc.actions[-1]["verdict"] = "expired_unapproved"
    inc.actions[-1]["t"] = 1_700_000_000
    inc.closed_t += 120
    assert "Approval expired after 120 s. Escalated." in format_incident(inc)


def test_every_outgoing_field_is_redacted(monkeypatch):
    monkeypatch.setenv("CHAOS_TOKEN", "sample-private-value")
    inc = incident()
    inc.id = "person@example.com"
    inc.services = ["10.1.2.3"]
    inc.report["permanent_fix"] = "rotate password=unsafe-value and sample-private-value"
    out = format_incident(inc)
    for secret in ("person@example.com", "10.1.2.3", "unsafe-value", "sample-private-value"):
        assert secret not in out
    assert "[REDACTED]" in out


def test_missing_diagnosis_and_abstention_do_not_claim_confidence():
    inc = Incident(id="i2", opened_t=0, likely_cause="insufficient_evidence",
                   confidence=0.91, abstained=True, status="escalated")
    out = format_incident(inc, show_probability=True)
    assert "Confidence:" not in out
    assert "no specific signal recorded" in out
    assert "human review needed" in out
    assert "Escalated for human review" in out
