"""Approval reliability: the engine lock is held only to read and write shared state, never while diagnosis waits on telemetry,
Docker or logs. GET /approvals (and /incidents) must answer quickly while a slow diagnosis is in progress."""
import threading
import time

from fastapi.testclient import TestClient

from engine import api
from tests.test_autopilot_path import FakeInvestigator, make_engine
from engine.engine import Incident

SLOW_S = 1.5


def slow_investigator(started: threading.Event):
    class Slow(FakeInvestigator):
        def __getattr__(self, name):
            def call(*a, **k):
                if name == "metrics":            # one evidence tool that blocks like a slow Prometheus/Docker call
                    started.set()
                    time.sleep(SLOW_S)
            return call
    return Slow


def test_get_approvals_answers_in_under_200_ms_while_a_diagnosis_runs(monkeypatch):
    e = make_engine("ask-first", "orders", "error_spike", monkeypatch)
    started = threading.Event()
    monkeypatch.setattr("engine.engine.Investigator", slow_investigator(started))
    pending = Incident("pend", 900.0)                     # a proposal already waiting for a human
    pending.services, pending.diagnosed, pending.status = ["payments"], True, "awaiting_approval"
    pending.actions.append({"t": time.time(), "runbook_id": "restart_service", "service": "payments", "verdict": "needs_approval",
                            "reason": "ask-first", "risk": "low", "executed": False, "approved_by": None})
    e.incidents.append(pending)
    diag = Incident("diag", 1000.0)
    diag.services = ["orders"]
    e.incidents.append(diag)
    monkeypatch.setattr(api, "engine", e)
    feats = {s: {"up_frac": 1.0} for s in ("web", "orders", "inventory", "payments")}
    t = threading.Thread(target=e._try_diagnose, args=(diag, feats, {s: 0.0 for s in feats}, {s: s == "orders" for s in feats}))
    t.start()
    assert started.wait(5), "diagnosis did not start"
    c = TestClient(api.app)
    t0 = time.perf_counter()
    r = c.get("/approvals")
    dt = time.perf_counter() - t0
    assert t.is_alive(), "the diagnosis must still be running during the request"
    assert r.status_code == 200 and [a["incident_id"] for a in r.json()] == ["pend"]
    assert dt < 0.2, f"GET /approvals took {dt:.3f} s while a diagnosis was running"
    t1 = time.perf_counter()
    assert c.get("/incidents").status_code == 200 and time.perf_counter() - t1 < 0.2
    t.join(10)
    assert diag.diagnosed and diag.actions and diag.actions[-1]["verdict"] == "needs_approval"   # the result is still applied


def test_a_diagnosis_result_is_dropped_if_the_incident_was_closed_meanwhile(monkeypatch):
    e = make_engine("autopilot", "web", "down", monkeypatch)
    started, release = threading.Event(), threading.Event()

    class Gate(FakeInvestigator):
        def __getattr__(self, name):
            def call(*a, **k):
                if name == "metrics":
                    started.set()
                    release.wait(5)
            return call
    monkeypatch.setattr("engine.engine.Investigator", Gate)
    inc = Incident("x", 1000.0)
    inc.services = ["web"]
    e.incidents.append(inc)
    feats = {s: {"up_frac": 1.0} for s in ("web", "orders", "inventory", "payments")}
    t = threading.Thread(target=e._try_diagnose, args=(inc, feats, {s: 0.0 for s in feats}, {s: s == "web" for s in feats}))
    t.start()
    assert started.wait(5)
    with e.lock:                                         # e.g. POST /admin/reset closed it while the diagnosis was computing
        inc.status, inc.closed_t = "escalated", 1001.0
    release.set()
    t.join(10)
    assert inc.actions == [] and e.executor.calls == [] and not inc.diagnosed
