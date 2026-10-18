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


def test_token_never_comes_from_the_polluted_environment_variable(monkeypatch):
    monkeypatch.setenv("ETERNALAI_APPROVAL_TOKEN", "change-me")          # what load_dotenv() put there in v1
    monkeypatch.delenv("EAI_BENCH_TOKEN", raising=False)
    assert rb.benchmark_token() == "benchmark-token-not-a-secret"
    monkeypatch.setenv("EAI_BENCH_TOKEN", "my-own")
    assert rb.benchmark_token() == "my-own"


def test_mechanism_of_v1_importing_eternalai_config_loads_dotenv_into_the_environment(tmp_path):
    """Deterministic proof of the v1 cause: with a .env that defines the placeholder, merely importing eternalai.config puts it in os.environ."""
    import subprocess
    import sys
    (tmp_path / ".env").write_text("ETERNALAI_APPROVAL_TOKEN=change-me" + chr(10))
    root = Path(__file__).resolve().parents[1]
    code = f"import sys, os; sys.path.insert(0, r'{root}'); import eternalai.config; print(os.environ.get('ETERNALAI_APPROVAL_TOKEN'))"
    env = {k: v for k, v in __import__("os").environ.items() if k != "ETERNALAI_APPROVAL_TOKEN"}
    out = subprocess.run([sys.executable, "-c", code], cwd=tmp_path, capture_output=True, text=True, env=env).stdout.strip()
    assert out == "change-me"


def test_verify_approval_api_accepts_409_and_aborts_on_503_or_403(monkeypatch):
    import pytest
    patch(monkeypatch, None, lambda url, **kw: resp(409, {"detail": "no pending approval"}))
    assert rb.verify_approval_api("t") is True
    for code in (503, 403):
        patch(monkeypatch, None, lambda url, _c=code, **kw: resp(_c, {"detail": "x"}))
        with pytest.raises(SystemExit) as e:
            rb.verify_approval_api("t")
        assert str(code) in str(e.value)
