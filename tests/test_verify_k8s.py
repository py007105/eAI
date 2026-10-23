from types import SimpleNamespace as NS
from unittest.mock import Mock

import httpx

from eternalai.verify_k8s import probe_once, verify_recovery_k8s


def deployment(ready, desired=1):
    return NS(spec=NS(replicas=desired), status=NS(ready_replicas=ready))


def test_root_and_all_callers_must_be_ready_before_frontend_probe():
    apps = Mock()
    apps.read_namespaced_deployment.side_effect = [deployment(1), deployment(0)]
    requests = []
    client = httpx.Client(transport=httpx.MockTransport(lambda req: requests.append(req) or httpx.Response(200)))
    ok, _duration, detail = probe_once("cartservice", {"frontend": ["cartservice"], "cartservice": []},
                                       "shop", apps, client, "http://frontend.shop")
    assert not ok and "frontend" in detail and not requests
    assert apps.read_namespaced_deployment.call_args_list[0].args == ("cartservice", "shop")
    assert apps.read_namespaced_deployment.call_args_list[1].args == ("frontend", "shop")


def test_recovered_requires_frontend_http_200_through_window(monkeypatch):
    apps = Mock()
    apps.read_namespaced_deployment.return_value = deployment(1)
    client = httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(200)))
    clock = {"t": 0.0}
    monkeypatch.setattr("eternalai.verify_k8s.time.monotonic", lambda: clock["t"])
    monkeypatch.setattr("eternalai.verify_k8s.time.sleep", lambda interval: clock.__setitem__("t", clock["t"] + interval))
    result = verify_recovery_k8s("frontend", {"frontend": []}, "shop", observation_s=2,
                                  frontend_url="http://frontend.shop", apps=apps, client=client)
    assert result["outcome"] == "recovered" and result["probes"] == 2
    assert result["success_rate"] == 1.0
