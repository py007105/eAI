"""verify.py: one checkout probe, and the recovered / partially_recovered / unresolved verdict over a window. No network."""
import httpx

from eternalai import verify
from eternalai.verify import Probe, checkout_probe


def client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_confirmed_order_is_a_good_probe():
    seen = {}

    def h(req):
        seen["path"], seen["body"] = req.url.path, req.content
        return httpx.Response(200, json={"status": "confirmed", "order_id": 1})
    p = checkout_probe(client(h), base="http://web")
    assert p.ok and p.detail == "HTTP 200" and seen["path"] == "/api/checkout"


def test_failed_probes():
    assert not checkout_probe(client(lambda r: httpx.Response(503)), base="http://web").ok
    assert not checkout_probe(client(lambda r: httpx.Response(200, json={"status": "rejected"})), base="http://web").ok
    assert not checkout_probe(client(lambda r: httpx.Response(200, text="not json")), base="http://web").ok

    def down(req):
        raise httpx.ConnectError("refused", request=req)
    p = checkout_probe(client(down), base="http://web")
    assert not p.ok and p.detail == "ConnectError"


def run_with(monkeypatch, probes):
    """verify_recovery with a fake clock: one probe per second, the probes given in order."""
    clock = {"t": 0.0}
    seq = iter(probes)
    monkeypatch.setattr(verify.time, "time", lambda: clock["t"])
    monkeypatch.setattr(verify.time, "sleep", lambda s: clock.__setitem__("t", clock["t"] + s))
    monkeypatch.setattr(verify, "checkout_probe", lambda c: next(seq))
    return verify.verify_recovery(observation_s=len(probes), interval_s=1.0, latency_budget_s=1.0)


def good(lat=0.1):
    return Probe(True, lat, "HTTP 200")


def bad():
    return Probe(False, 0.1, "HTTP 503")


def test_all_good_is_recovered(monkeypatch):
    v = run_with(monkeypatch, [good()] * 20)
    assert v["outcome"] == "recovered" and v["probes"] == 20 and v["success_rate"] == 1.0


def test_one_slow_probe_is_not_full_recovery(monkeypatch):
    v = run_with(monkeypatch, [good()] * 19 + [good(lat=1.5)])        # over the 1 s latency budget
    assert v["outcome"] == "partially_recovered" and v["p_max_latency_s"] == 1.5


def test_half_is_partial_and_less_is_unresolved(monkeypatch):
    assert run_with(monkeypatch, [good(), bad()] * 10)["outcome"] == "partially_recovered"
    assert run_with(monkeypatch, [good()] * 9 + [bad()] * 11)["outcome"] == "unresolved"
    v = run_with(monkeypatch, [bad()] * 20)
    assert v["outcome"] == "unresolved" and v["last_detail"] == "HTTP 503"
