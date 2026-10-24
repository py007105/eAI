"""Harness scripts send the evaluator token and stop (without printing it) when it is missing or refused."""
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import harness_auth  # noqa: E402

HARNESS = ["models/collect_runs.py", "scripts/diag_approver.py", "scripts/evaluator_smoke.py", "scripts/forecast_check.py",
           "scripts/rollback_check.py", "scripts/safe_collect.py", "scripts/surge_capture.py", "scripts/run_benchmark.py"]


def test_token_from_env(monkeypatch):
    monkeypatch.delenv("EAI_EVALUATOR_TOKEN", raising=False)
    monkeypatch.setenv("ETERNALAI_APPROVAL_TOKEN", "abc-123-xyz")
    assert harness_auth.evaluator_headers() == {"X-Approval-Token": "abc-123-xyz"}
    monkeypatch.setenv("EAI_EVALUATOR_TOKEN", "eval-only-456")
    assert harness_auth.evaluator_token() == "eval-only-456"


@pytest.mark.parametrize("value", ["", "change-me"])
def test_missing_or_placeholder_token_stops_without_echo(monkeypatch, value):
    monkeypatch.delenv("EAI_EVALUATOR_TOKEN", raising=False)
    monkeypatch.setenv("ETERNALAI_APPROVAL_TOKEN", value)
    with pytest.raises(SystemExit) as e:
        harness_auth.evaluator_token()
    assert "token" in str(e.value)


def test_refused_token_stops_without_echo(monkeypatch):
    monkeypatch.setenv("EAI_EVALUATOR_TOKEN", "secret-value-789")
    for code in (403, 503):
        with pytest.raises(SystemExit) as e:
            harness_auth.check_started(httpx.Response(code))
        assert "secret-value-789" not in str(e.value)
    ok = httpx.Response(200)
    assert harness_auth.check_started(ok) is ok


def test_every_harness_script_sends_the_header():
    root = Path(__file__).resolve().parents[1]
    for f in HARNESS:
        src = (root / f).read_text(encoding="utf-8")
        assert 'httpx.post(f"{EV}/runs", headers=evaluator_headers()' in src, f
    assert 'call("POST", f"{EV}/runs", token,' in (root / "scripts/rehearsal.py").read_text(encoding="utf-8")
