from types import SimpleNamespace as NS
from unittest.mock import Mock

import httpx

from eternalai.engine import Engine, Incident


def test_kubernetes_app_snapshot_uses_frontend_not_docker_checkout(monkeypatch):
    engine = Engine.__new__(Engine)
    engine.executor = NS(runtime="kubernetes")
    engine.dv = NS(namespace="shop")
    requests = []
    real_client = httpx.Client
    monkeypatch.setattr(httpx, "Client", lambda *a, **k: real_client(
        transport=httpx.MockTransport(lambda req: requests.append(req) or httpx.Response(200))))
    snapshot = engine._app_snapshot(probe=True)
    assert snapshot == {"error_ratio": None, "p95_s": None, "checkout_success": 1.0}
    assert len(requests) == 3
    assert all(request.url.path == "/" and request.url.host == "frontend.shop.svc.cluster.local"
               for request in requests)


def test_kubernetes_action_uses_target_and_callers_verifier(monkeypatch):
    engine = Engine.__new__(Engine)
    engine.executor = NS(runtime="kubernetes", run=lambda *a, **k: {"ok": True}, log_verification=Mock())
    engine.dv = NS(namespace="shop")
    engine.policy = NS(record_execution=lambda service: None)
    engine._app_snapshot = lambda probe: {"checkout_success": 1.0}
    engine._preserve = lambda incident: None
    engine.persist = NS(runs={})
    engine.first_anom = {}
    called = {}

    def verify(service, graph, namespace, seconds):
        called.update(service=service, namespace=namespace, seconds=seconds)
        return {"outcome": "unresolved", "success_rate": 0.0, "probes": 1}

    monkeypatch.setattr("eternalai.engine.verify_recovery_k8s", verify)
    monkeypatch.setattr("eternalai.engine.verify_recovery", lambda *a: (_ for _ in ()).throw(AssertionError("Docker probe")))
    monkeypatch.setattr("eternalai.engine.time.sleep", lambda *a: None)
    incident = Incident("i1", 0)
    incident.likely_cause = "bad_deploy"
    act = {"runbook_id": "rollback_release", "service": "frontend", "reason": "unready"}
    engine._act_and_verify(incident, act, "human:operator")
    assert called["service"] == "frontend" and called["namespace"] == "shop"
    assert incident.verification["outcome"] == "unresolved"
    engine.executor.log_verification.assert_called_once()
