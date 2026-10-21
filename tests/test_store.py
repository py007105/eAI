"""Learn store (SQLite): closed incidents, actions, outcomes and human feedback; training-row export; the engine writes closed
incidents outside its lock; POST /feedback is token-protected."""
import pytest
from fastapi.testclient import TestClient

from eternalai.store import LearnStore, StoreError
from tests.test_autopilot_path import diagnose, make_engine


def store(tmp_path):
    return LearnStore(f"sqlite:///{(tmp_path / 'learn.db').as_posix()}")


def closed_incident(iid="i1", executed=True, outcome="recovered"):
    return {"id": iid, "opened_t": 100.0, "closed_t": 160.0, "kind": "reactive", "status": outcome, "services": ["orders"],
            "ranking": [{"service": "orders", "score": 0.9}], "likely_cause": "memory_leak", "confidence": 0.93, "abstained": False,
            "diagnosis": {"root": "orders", "top_class": "memory_leak"}, "root_features": {"mem_rel_growth": 0.8},
            "report": {"summary": "orders memory leak"},
            "actions": [{"t": 110.0, "runbook_id": "recreate_container", "service": "orders", "verdict": "needs_approval",
                         "risk": "high", "reason": "x", "executed": executed, "executed_t": 120.0, "approved_by": "alice",
                         "result": {"ok": True}}],
            "verification": {"outcome": outcome, "success_rate": 1.0, "probes": 20, "t": 150.0},
            "before": {"checkout_success": 0.33}, "after": {"checkout_success": 1.0}}


def test_record_read_and_export(tmp_path):
    s = store(tmp_path)
    s.record_incident(closed_incident())
    s.record_incident(closed_incident())                          # upsert, not a duplicate
    rec = s.incident("i1")
    assert rec["root"] == "orders" and len(rec["actions"]) == 1 and rec["outcome"]["time_to_verified_s"] == 30.0
    assert s.counts() == {"incidents": 1, "actions": 1, "outcomes": 1, "feedback": 0}
    a, c = s.training_rows()
    assert a[0]["label"] is None and a[0]["mem_rel_growth"] == 0.8          # no human yet: no label
    assert c[0]["fix"] == "recreate_container" and c[0]["outcome"] == "recovered" and c[0]["fault_source"] == "diagnosis"


def test_feedback_labels_rows(tmp_path):
    s = store(tmp_path)
    s.record_incident(closed_incident())
    with pytest.raises(StoreError):
        s.add_feedback("nope", "alice", True, None, "")
    s.add_feedback("i1", "alice", True, None, "right call")
    assert s.training_rows()[0][0]["label"] == "memory_leak"
    s.add_feedback("i1", "bob", False, "disk_fill", "it was the disk")    # the latest feedback wins
    a, c = s.training_rows()
    assert a[0]["label"] == "disk_fill" and a[0]["label_source"] == "human" and c[0]["fault"] == "disk_fill"


def test_only_sqlite_urls():
    with pytest.raises(StoreError, match="sqlite"):
        LearnStore("postgresql://u:p@db/eai")


def test_engine_stores_closed_incidents_with_root_features(tmp_path, monkeypatch):
    e = make_engine("ask-first", "orders", "down", monkeypatch)
    e.store = store(tmp_path)
    inc = diagnose(e, "orders")                    # awaiting approval: not closed, not stored
    e._store_closed()
    assert e.store.counts()["incidents"] == 0
    e.reject(inc.id, "alice")                      # closed (escalated)
    e._store_closed()
    e._store_closed()
    rec = e.store.incident(inc.id)
    assert rec["status"] == "escalated" and rec["actions"][0]["verdict"] == "rejected_by_alice"
    assert e.store.counts()["incidents"] == 1 and "up_frac" in rec["root_features"]


def test_feedback_endpoint(tmp_path, monkeypatch):
    from eternalai import api
    monkeypatch.setenv("ETERNALAI_APPROVAL_TOKEN", "fb-token-1234")
    e = make_engine("ask-first", "orders", "down", monkeypatch)
    e.store = store(tmp_path)
    e.store.record_incident(closed_incident("i9"))
    monkeypatch.setattr(api, "engine", e)
    c, h = TestClient(api.app), {"X-Approval-Token": "fb-token-1234"}
    body = {"approver": "alice", "confirmed": False, "correct_fault": "disk_fill", "note": "disk"}
    assert c.post("/feedback/i9", json=body).status_code == 403
    assert c.post("/feedback/zzz", json=body, headers=h).status_code == 404
    assert c.post("/feedback/i9", json={"confirmed": False}, headers=h).status_code == 400
    assert c.post("/feedback/i9", json={**body, "correct_fault": "DROP TABLE"}, headers=h).status_code == 422
    assert c.post("/api/feedback/i9", json=body, headers=h).json()["ok"] is True
    assert c.get("/learn/i9").json()["feedback"][0]["correct_fault"] == "disk_fill"
    assert c.get("/learn/stats").json()["feedback"] == 1


def test_export_script(tmp_path):
    import subprocess
    import sys
    from pathlib import Path
    s = store(tmp_path)
    s.record_incident(closed_incident())
    s.add_feedback("i1", "alice", True, None, "")
    root = Path(__file__).resolve().parents[1]
    r = subprocess.run([sys.executable, str(root / "scripts" / "export_learn_store.py"), "--db", str(s.path), "--out", str(tmp_path / "x")],
                       capture_output=True, text=True)
    assert r.returncode == 0 and "1 human-labelled" in r.stdout
    head = (tmp_path / "x" / "A_learned_rows.csv").read_text(encoding="utf-8").splitlines()
    assert head[0].startswith("incident_id,root,label,label_source") and "memory_leak" in head[1]
