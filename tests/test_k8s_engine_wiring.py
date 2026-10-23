from types import SimpleNamespace as NS
from unittest.mock import Mock
import threading

import httpx

from eternalai import config
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


def test_kubernetes_bad_image_evidence_selects_approval_gated_rollback(monkeypatch):
    class QuietInvestigator:
        def __init__(self, *args):
            self.items = []

        def __getattr__(self, name):
            return lambda *args, **kwargs: None

    monkeypatch.setattr("eternalai.engine.Investigator", QuietInvestigator)
    engine = Engine.__new__(Engine)
    engine.lock = threading.RLock()
    engine.executor = NS(runtime="kubernetes")
    engine.dv = NS(state=lambda: {}, image_pull_failure=lambda service: service == "web")
    engine.prom = None
    engine.detectors = engine.classifier = engine.ranker = None
    engine.root_margin = None
    engine.frames = {name: None for name in config.SERVICES}
    engine._depfail = lambda: {}
    features = {name: {"up_frac": 0.0} for name in config.SERVICES}
    result = engine._diagnose_compute(["web"], {"web": 1.0}, features,
                                      {name: 0.0 for name in config.SERVICES},
                                      {name: name == "web" for name in config.SERVICES})
    assert result["label"] == "bad_deploy"
    assert result["report"].runbook_id == "rollback_release"
    assert result["diagnosis"]["image_pull_failure"]


def test_unknown_kubernetes_services_report_model_fallbacks(monkeypatch):
    monkeypatch.setattr(config, "load_topology", lambda: config.TOPOLOGY)
    monkeypatch.setattr("eternalai.engine.make_sources", lambda: (None, None))
    monkeypatch.setattr("eternalai.engine.make_driver", lambda: NS(runtime="kubernetes"))
    monkeypatch.setattr("eternalai.engine.LearnStore", lambda: NS())

    def load(name):
        if name == "detectors":
            return {"unrelated-service": object()}, {}
        return object(), {}

    monkeypatch.setattr("eternalai.engine.artifacts.load", load)
    engine = Engine()
    assert engine.models_loaded == {"detectors": False, "classifier": False,
                                     "ranker": False, "baselines": False}
