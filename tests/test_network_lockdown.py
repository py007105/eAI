"""Network lockdown: every published port is bound to 127.0.0.1; starting a fault (brain /challenge/start, evaluator POST /runs)
needs the approval token; the evaluator and the shop services refuse to start with an unset or default CHAOS_TOKEN."""
import importlib
import re
import sys
import types
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")


def test_every_published_port_is_bound_to_localhost():
    ports = re.findall(r"ports:\s*\[([^\]]*)\]", COMPOSE)
    assert len(ports) == 6
    for p in ports:
        for mapping in re.findall(r'"([^"]+)"', p):
            assert mapping.startswith("127.0.0.1:"), mapping


def test_compose_requires_chaos_token_and_has_no_default():
    assert "evaluator-only}" not in COMPOSE and COMPOSE.count("${CHAOS_TOKEN:?") == 2


@pytest.fixture
def evaluator(tmp_path, monkeypatch):
    monkeypatch.setenv("TRUTH_DIR", str(tmp_path / "truth"))
    monkeypatch.syspath_prepend(str(ROOT / "evaluator"))

    def load(chaos):
        if chaos is None:
            monkeypatch.delenv("CHAOS_TOKEN", raising=False)
        else:
            monkeypatch.setenv("CHAOS_TOKEN", chaos)
        for m in ("main", "scoring", "timing", "scenarios"):
            sys.modules.pop(m, None)
        scenarios = importlib.import_module("scenarios")
        monkeypatch.setattr(scenarios, "Injector", lambda token: types.SimpleNamespace(token=token))   # no Docker in tests
        return importlib.import_module("main")
    yield load
    for m in ("main", "scoring", "timing", "scenarios"):
        sys.modules.pop(m, None)


@pytest.mark.parametrize("chaos", [None, "", "evaluator-only"])
def test_evaluator_refuses_to_start_without_a_real_chaos_token(evaluator, chaos):
    with pytest.raises(RuntimeError, match="CHAOS_TOKEN"):
        evaluator(chaos)


def test_evaluator_post_runs_needs_the_approval_token(evaluator, monkeypatch):
    main = evaluator("test-chaos-token")
    monkeypatch.setenv("ETERNALAI_APPROVAL_TOKEN", "test-token-123")
    started = []
    monkeypatch.setattr(main.threading, "Thread", lambda target, args, daemon: types.SimpleNamespace(start=lambda: started.append(args)))
    c = TestClient(main.app)
    body = {"scenario": "latency", "target": "web"}
    assert c.post("/runs", json=body).status_code == 403
    assert c.post("/runs", json=body, headers={"X-Approval-Token": "wrong"}).status_code == 403
    assert started == []                                                      # nothing injected
    r = c.post("/runs", json=body, headers={"X-Approval-Token": "test-token-123"})
    assert r.status_code == 200 and len(started) == 1


def test_evaluator_refuses_runs_while_the_token_is_the_placeholder(evaluator, monkeypatch):
    main = evaluator("test-chaos-token")
    monkeypatch.setenv("ETERNALAI_APPROVAL_TOKEN", "change-me")
    assert TestClient(main.app).post("/runs", json={}, headers={"X-Approval-Token": "change-me"}).status_code == 503


@pytest.mark.parametrize("chaos", [None, "evaluator-only"])
def test_shop_services_refuse_to_start_without_a_real_chaos_token(monkeypatch, chaos):
    stub = types.ModuleType("prometheus_client")   # the real package is only installed in the service image
    for name in ("Counter", "Gauge", "Histogram", "generate_latest"):
        setattr(stub, name, lambda *a, **k: None)
    stub.CONTENT_TYPE_LATEST = "text/plain"
    monkeypatch.setitem(sys.modules, "prometheus_client", stub)
    monkeypatch.syspath_prepend(str(ROOT / "services" / "shop" / "common"))
    if chaos is None:
        monkeypatch.delenv("CHAOS_TOKEN", raising=False)
    else:
        monkeypatch.setenv("CHAOS_TOKEN", chaos)
    sys.modules.pop("obs", None)
    with pytest.raises(RuntimeError, match="CHAOS_TOKEN"):
        importlib.import_module("obs")
    sys.modules.pop("obs", None)


def test_brain_challenge_start_needs_the_token_and_forwards_it(monkeypatch):
    from engine import api
    monkeypatch.setenv("ETERNALAI_APPROVAL_TOKEN", "test-token-123")
    sent = []

    class R:
        status_code = 200

        def json(self):
            return {"run_id": "r1", "blind": True}
    monkeypatch.setattr(api.httpx, "post", lambda url, **k: sent.append(k.get("headers")) or R())
    c = TestClient(api.app)
    assert c.post("/challenge/start").status_code == 403 and sent == []
    r = c.post("/challenge/start", headers={"X-Approval-Token": "test-token-123"})
    assert r.status_code == 200 and sent == [{"X-Approval-Token": "test-token-123"}]
