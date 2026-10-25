"""Regression: an exception during diagnosis once left an incident 'open' forever, which blocked every later incident
(found by the live smoke test on the threshold baseline). The engine must escalate instead."""
import threading

from engine.engine import Engine, Incident


def bare_engine():
    e = Engine.__new__(Engine)             # no Docker or Prometheus needed for this unit test
    e.lock, e.last_error, e.last_closed = threading.RLock(), None, {}
    e.preserved = []
    e._preserve = lambda inc: e.preserved.append(inc.id)
    return e


def test_exception_in_diagnosis_escalates_and_preserves_evidence():
    e = bare_engine()

    def boom(*a):
        raise IndexError("list index out of range")
    e._diagnose = boom
    inc = Incident("i1", 100.0)
    e._try_diagnose(inc, {}, {}, {})
    assert inc.status == "escalated" and inc.closed_t is not None and inc.diagnosed
    assert "diagnosis failed" in e.last_error and e.preserved == ["i1"]


def test_normal_diagnosis_is_untouched():
    e = bare_engine()
    e._diagnose = lambda inc, *a: setattr(inc, "diagnosed", True)
    inc = Incident("i2", 100.0)
    e._try_diagnose(inc, {}, {}, {})
    assert inc.status == "open" and inc.diagnosed and e.preserved == []
