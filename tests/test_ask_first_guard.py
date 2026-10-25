import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("g", Path(__file__).resolve().parents[1] / "tools" / "ask_first_guard.py")
g = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g)


def row(**kw):
    base = {"arm": "eternalai_ask_first", "scenario": "crash", "seed": 1, "score": {"detected": True},
            "approver": {"approved": 1, "approve_failures": 0, "poll_errors": 0, "thread_errors": 0},
            "incidents": [{"id": "i1", "status": "closed", "actions": [{"runbook_id": "restart", "verdict": "executed"}]}]}
    base.update(kw)
    return base


def test_valid_row_and_other_arms_are_ignored():
    assert g.check_row(row()) == ([], [])
    assert g.check_row(row(arm="eternalai_autopilot", approver=None)) == ([], [])


def test_approve_failures_and_errors_are_invalid():
    p, _ = g.check_row(row(approver={"approve_failures": 2, "poll_errors": 0, "thread_errors": 0}))
    assert p and "approve_failures=2" in p[0]
    assert g.check_row(row(approver={"approve_failures": 0, "poll_errors": 1, "thread_errors": 0}))[0]


def test_expired_unapproved_and_pending_incident_are_invalid():
    exp = row(incidents=[{"id": "i2", "status": "open", "actions": [{"runbook_id": "restart", "verdict": "expired_unapproved"}]}])
    assert "expired unapproved" in g.check_row(exp)[0][0]
    assert g.check_row(row(incidents=[{"id": "i3", "status": "awaiting_approval", "actions": []}]))[0]


def test_undetected_supported_fault_is_only_a_warning_and_healthy_runs_are_not():
    p, w = g.check_row(row(score={"detected": False}))
    assert p == [] and w
    assert g.check_row(row(scenario="traffic_surge", score={"detected": False}, incidents=[])) == ([], [])


def test_healthy_ask_first_row_without_approver_activity_is_valid():
    assert g.check_row(row(scenario="good_deploy", incidents=[], approver={"approved": 0, "approve_failures": 0, "poll_errors": 0, "thread_errors": 0})) == ([], [])
