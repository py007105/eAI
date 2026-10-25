"""api.py: every brain endpoint against a real engine object with fake telemetry and executor (no Docker, no Prometheus)."""
import pytest
from fastapi.testclient import TestClient

from engine import api
from tests.test_autopilot_path import diagnose, make_engine

TOKEN = "api-test-token-42"
H = {"X-Approval-Token": TOKEN}


@pytest.fixture
def ctx(monkeypatch):
    monkeypatch.setenv("ETERNALAI_APPROVAL_TOKEN", TOKEN)
    e = make_engine("ask-first", "orders", "down", monkeypatch)
    e.models_loaded = {"detectors": False, "classifier": True, "ranker": True, "baselines": False}
    e.det_meta, e.rank_meta = None, None
    e.cls_meta = {"trained_at_utc": "t", "git_commit": "c", "ece_oof": 0.003, "show_probability_in_ui": True, "data_hash": "h"}
    e.latest, e.depfail, e.telemetry_failed = {"web": {"anomalous": False}}, {("orders", "payments"): 1.0}, {}
    e.executor.audit = [{"t": i} for i in range(150)]
    monkeypatch.setattr(api, "engine", e)
    return e, TestClient(api.app)


def test_read_endpoints(ctx):
    e, c = ctx
    inc = diagnose(e, "orders")
    assert c.get("/health").json() == {"ok": True}
    st = c.get("/status").json()
    assert st["mode"] == "ask-first" and st["open_incidents"] == 1 and st["fallbacks_in_use"] == ["detectors", "baselines"]
    assert st["policy"]["file"] == "default.yaml" and st["policy"]["auto_allowed_risks"] == ["low"]
    assert st["calibration"]["show_probability"] is True and st["kill_switch"] is False
    assert c.get("/services").json()["depfail"] == {"orders->payments": 1.0}
    assert [i["id"] for i in c.get("/incidents").json()] == [inc.id]
    assert c.get(f"/incidents/{inc.id}").json()["likely_cause"] == "down"
    assert c.get("/incidents/nope").status_code == 404
    ap = c.get("/approvals").json()
    assert len(ap) == 1 and ap[0]["service"] == "orders" and ap[0]["runbook_id"] == "restart_service"
    assert len(c.get("/audit").json()) == 100


def test_actions_need_a_real_token(ctx, monkeypatch):
    e, c = ctx
    inc = diagnose(e, "orders")
    for path, body in ((f"/approvals/{inc.id}/approve", {"approver": "x"}), (f"/approvals/{inc.id}/reject", {"approver": "x"}),
                       ("/mode", {"mode": "autopilot"}), ("/admin/reset", None), ("/killswitch", {"on": True})):
        assert c.post(path, json=body).status_code == 403, path
        assert c.post(path, json=body, headers={"X-Approval-Token": "wrong"}).status_code == 403, path
    monkeypatch.setenv("ETERNALAI_APPROVAL_TOKEN", "change-me")
    assert c.post(f"/approvals/{inc.id}/approve", json={}, headers={"X-Approval-Token": "change-me"}).status_code == 503
    assert e.executor.calls == []


def test_approve_reject_mode_reset(ctx):
    e, c = ctx
    inc = diagnose(e, "orders")
    assert c.post("/approvals/other/approve", json={"approver": "op"}, headers=H).status_code == 409
    assert c.post(f"/approvals/{inc.id}/approve", json={"approver": "op"}, headers=H).json() == {"ok": True}
    assert e.executor.calls == [("restart_service", "orders", "human:op")]
    inc2 = diagnose(e, "web")
    assert c.post(f"/approvals/{inc2.id}/reject", json={"approver": "op"}, headers=H).json() == {"ok": True}
    assert inc2.status == "escalated"
    assert c.post("/mode", json={"mode": "sometimes"}, headers=H).status_code == 400
    assert c.post("/mode", json={"mode": "watch"}, headers=H).json() == {"mode": "watch-only"}
    inc.status = "open"
    out = c.post("/admin/reset", headers=H).json()
    assert out["reset"] is True and inc.id in out["closed_incidents"]
