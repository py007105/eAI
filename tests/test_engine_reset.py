"""v2 item D: reset between benchmark runs (v1 carried a cooldown from one run into the next; docs/postmortems/benchmark-v1-triage.md, crash seed 130)."""
import threading

import pytest

from eternalai.dedupe import Suppressor
from eternalai.detect import Persistence
from eternalai.engine import Engine, Incident
from eternalai import config, rulebook
from eternalai.policy import PolicyEngine

V2 = rulebook.load(rulebook.RULEBOOK_DIR / "benchmark-v2.yaml", config.SERVICES)   # cooldown 90 s, as in v1/v2


def engine():
    e = Engine.__new__(Engine)
    e.lock, e.last_error, e.preserved = threading.RLock(), None, []
    e._preserve = lambda inc: e.preserved.append(inc.id)
    e.policy, e.suppress, e.persist = PolicyEngine("autopilot", rulebook=V2, kill_switch=False, protected=set()), Suppressor(), Persistence(3)
    e.incidents, e.first_anom, e.last_closed = [], {"web": 1.0}, {"t": 5.0}
    return e


def test_reset_clears_cooldown_so_a_restart_is_no_longer_blocked():
    e = engine()
    e.policy.record_execution("inventory", now=100.0)
    assert e.policy.evaluate("restart_service", "inventory", now=185.0).verdict == "blocked"      # the v1 symptom: cooldown from the previous run
    e.reset_run_state()
    assert e.policy.evaluate("restart_service", "inventory", now=185.0).verdict == "execute"
    assert e.first_anom == {} and e.last_closed == {}


def test_reset_clears_breakers_suppression_and_persistence():
    e = engine()
    e.policy.breaker_open.add("orders")
    e.suppress.suppressed.add("orders")
    e.persist.runs["orders"] = 2
    e.reset_run_state()
    assert e.policy.breaker_open == set() and e.suppress.suppressed == set() and e.persist.runs == {}


def test_reset_clears_the_hourly_action_count():
    e = engine()
    e.policy.record_execution("web", now=1.0)
    assert e.policy.executed
    assert e.reset_run_state()["cleared"]["actions_this_hour"] == 1 and e.policy.executed == []


def test_reset_closes_open_and_pending_incidents_but_keeps_history():
    e = engine()
    a, b, c = Incident("a", 1.0), Incident("b", 2.0), Incident("c", 3.0)
    a.status, b.status, c.status = "open", "awaiting_approval", "recovered"
    e.incidents += [a, b, c]
    out = e.reset_run_state()
    assert out["closed_incidents"] == ["a", "b"] and e.preserved == ["a", "b"]
    assert [i.status for i in e.incidents] == ["escalated", "escalated", "recovered"] and len(e.incidents) == 3


def test_reset_is_refused_while_an_action_is_in_flight():
    e = engine()
    inc = Incident("x", 1.0)
    inc.status = "verifying"
    e.incidents.append(inc)
    e.policy.record_execution("web", now=1.0)
    with pytest.raises(ValueError):
        e.reset_run_state()
    assert e.policy.history                                  # nothing was cleared
