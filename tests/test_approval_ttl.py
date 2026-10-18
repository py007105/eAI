"""v2 / G1: a proposal nobody approves must expire and must never block detection (in v1 one unapproved proposal blocked every later incident:
docs/postmortems/ask-first-arm-stuck-incident-v1.md). The tests drive Engine.tick with the observation faked, so no Docker or Prometheus is needed."""
import threading

import pytest

from eternalai import config
from eternalai.engine import Engine, Incident


def engine(anom=None):
    e = Engine.__new__(Engine)
    e.lock, e.last_error, e.last_closed = threading.RLock(), None, {}
    e.incidents, e.first_anom, e.preserved = [], {}, []
    e._preserve = lambda inc: e.preserved.append(inc.id)
    e._predictive = lambda feats, now: None
    e.window_s = 10.0

    class Persist:                       # every anomaly is confirmed immediately
        def update(self, s, a):
            return bool(a)

    class Suppress:
        def note_incident(self, *a): ...
        def update(self, a): ...
        def filter(self, c): return c

    e.persist, e.suppress = Persist(), Suppress()
    e._observe = lambda: ({}, {}, anom if anom is not None else {})
    e._try_diagnose = lambda inc, *a: setattr(inc, "diagnosed", True)
    return e


def pending(inc_id, service, t, verdict="needs_approval", status="awaiting_approval"):
    inc = Incident(inc_id, t - 10)
    inc.services, inc.diagnosed, inc.status = [service], True, status
    inc.actions.append({"t": t, "runbook_id": "rollback_release", "service": service, "verdict": verdict, "executed": False, "approved_by": None})
    return inc


def test_unapproved_proposal_expires_escalates_and_preserves_evidence(monkeypatch):
    monkeypatch.setattr(config, "APPROVAL_TTL_S", 120.0)
    e = engine()
    inc = pending("p1", "payments", t=1000.0)
    e.incidents.append(inc)
    e._expire_pending(1119.0)
    assert inc.status == "awaiting_approval"                          # not yet
    e._expire_pending(1120.5)
    assert inc.status == "escalated" and inc.closed_t == 1120.5 and inc.actions[-1]["verdict"] == "expired_unapproved"
    assert e.preserved == ["p1"] and "expired" in inc.timeline[-1]["msg"]


def test_approve_after_expiry_is_refused():
    e = engine()
    inc = pending("p2", "payments", t=0.0)
    inc.status = "escalated"
    e.incidents.append(inc)
    with pytest.raises(ValueError):
        e.approve("p2", "benchmark-operator")


def test_pending_approval_does_not_block_a_new_incident_elsewhere(monkeypatch):
    monkeypatch.setattr(config, "APPROVAL_TTL_S", 120.0)
    e = engine(anom={"inventory": True})
    e.incidents.append(pending("p3", "payments", t=9.9e12))           # far future start: cannot expire in this test
    e.tick()
    opened = [i for i in e.incidents if i.id != "p3"]
    assert len(opened) == 1 and opened[0].services == ["inventory"] and e.incidents[0].status == "awaiting_approval"


def test_services_already_covered_by_a_pending_incident_do_not_open_a_duplicate():
    e = engine(anom={"payments": True, "orders": True, "web": True})   # orders and web call payments (directly or transitively)
    e.incidents.append(pending("p4", "payments", t=9.9e12))
    e.tick()
    assert [i.id for i in e.incidents] == ["p4"]


def test_a_service_that_does_not_depend_on_the_pending_one_still_opens():
    e = engine(anom={"inventory": True})                               # inventory is a callee of orders and web, not a caller of payments
    e.incidents.append(pending("p5", "payments", t=9.9e12))
    e.tick()
    assert len(e.incidents) == 2


def test_watch_only_observation_closes_after_ttl_and_does_not_block_forever(monkeypatch):
    monkeypatch.setattr(config, "APPROVAL_TTL_S", 60.0)
    e = engine()
    inc = pending("w1", "orders", t=100.0, verdict="observe_only", status="open")
    e.incidents.append(inc)
    e._expire_pending(159.0)
    assert inc.status == "open"
    e._expire_pending(161.0)
    assert inc.status == "escalated" and "watch-only" in inc.timeline[-1]["msg"] and inc.actions[-1]["verdict"] == "observe_only"


def test_an_undiagnosed_or_executing_incident_is_never_expired():
    e = engine()
    a = Incident("u1", 0.0)                                            # open, no action yet
    b = pending("x1", "web", t=0.0, verdict="execute", status="executing")
    e.incidents += [a, b]
    e._expire_pending(1e9)
    assert a.status == "open" and b.status == "executing"
