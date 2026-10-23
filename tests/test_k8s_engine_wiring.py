from types import SimpleNamespace as NS

import httpx

from eternalai.engine import Engine


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
