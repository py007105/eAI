"""v2 items C and D in the benchmark harness, with httpx mocked (no stack)."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace

spec = importlib.util.spec_from_file_location("rb", Path(__file__).resolve().parents[1] / "scripts" / "run_benchmark.py")
rb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rb)


class Once:
    """A stop event that lets the loop body run n times."""
    def __init__(self, n=1):
        self.n = n

    def is_set(self):
        self.n -= 1
        return self.n < 0


def resp(status, payload=None, text=""):
    return SimpleNamespace(status_code=status, json=lambda: payload, text=text or str(payload), headers={"content-type": "application/json"})


def patch(monkeypatch, get, post):
    monkeypatch.setattr(rb.httpx, "get", get)
    monkeypatch.setattr(rb.httpx, "post", post)
    monkeypatch.setattr(rb.time, "sleep", lambda s: None)


def test_approver_approves_and_counts(monkeypatch, capsys):
    pend = [{"incident_id": "i1", "runbook_id": "rollback_release", "service": "payments"}]
    posts = []
    patch(monkeypatch, lambda url, timeout: resp(200, pend), lambda url, **kw: posts.append(url) or resp(200, {"ok": True}))
    stats = {}
    rb.approver(Once(2), "tok", 0, stats)
    assert stats["approved"] == 1 and len(posts) == 1                      # approved once, not on every poll
    assert "APPROVER approved i1" in capsys.readouterr().out


def test_approver_logs_a_refused_approval_instead_of_swallowing_it(monkeypatch, capsys):
    pend = [{"incident_id": "i2", "runbook_id": "restart_service", "service": "web"}]
    patch(monkeypatch, lambda url, timeout: resp(200, pend), lambda url, **kw: resp(403, None, "invalid approval token"))
    stats = {}
    rb.approver(Once(1), "wrong", 0, stats)
    assert stats["approve_failures"] == 1 and stats["last_status"] == 403 and stats["approved"] == 0
    assert "HTTP 403" in capsys.readouterr().out


def test_approver_survives_and_logs_an_unexpected_exception(monkeypatch, capsys):
    patch(monkeypatch, lambda url, timeout: resp(200, "not a list of dicts"), lambda url, **kw: resp(200))
    stats = {}
    rb.approver(Once(2), "tok", 0, stats)                                  # v1: a TypeError here silently killed the thread
    assert stats["thread_errors"] >= 1 and "APPROVER unexpected" in capsys.readouterr().out


def test_approver_waits_the_configured_delay(monkeypatch):
    pend = [{"incident_id": "i3", "runbook_id": "r", "service": "s"}]
    posts = []
    patch(monkeypatch, lambda url, timeout: resp(200, pend), lambda url, **kw: posts.append(url) or resp(200))
    rb.approver(Once(2), "tok", 3600, {})
    assert posts == []


def test_reset_brain_returns_on_success_on_404_and_after_retries(monkeypatch, capsys):
    patch(monkeypatch, None, lambda url, **kw: resp(200, {"reset": True}))
    assert rb.reset_brain("t")["status"] == 200
    patch(monkeypatch, None, lambda url, **kw: resp(404, {"detail": "Not Found"}))
    assert rb.reset_brain("t")["status"] == 404                            # no retries against a brain without the endpoint
    calls = []
    patch(monkeypatch, None, lambda url, **kw: calls.append(1) or resp(409, {"detail": "busy"}))
    out = rb.reset_brain("t", tries=3)
    assert out["status"] == 409 and len(calls) == 3 and "RESET failed" in capsys.readouterr().out
