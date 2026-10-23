import httpx
import numpy as np

from eternalai.collector import Q
from eternalai.sources.k8s_metrics import KubernetesProm, QUERIES, UNOBSERVED


def test_kubernetes_metrics_match_schema_and_preserve_missing_http_signals():
    seen = []

    def respond(req):
        seen.append((req.url.params["query"], req.headers.get("Authorization")))
        start = float(req.url.params["start"])
        return httpx.Response(200, json={"status": "success", "data": {"result": [
            {"values": [[start, "1"], [start + 2, "1"]]}]}})

    client = httpx.Client(base_url="http://prom", transport=httpx.MockTransport(respond),
                          headers={"Authorization": "Bearer private"})
    source = KubernetesProm("http://prom", "shop", client=client)
    frame = source.signals("frontend", seconds=4, end=1000.0)
    assert list(frame) == list(Q)
    assert set(UNOBSERVED) == {"req_rate", "err_rate", "p95_s", "dep_fail_rate", "error_log_rate", "scratch_bytes"}
    assert frame[list(UNOBSERVED)].isna().all().all()
    assert all(frame[name].notna().any() for name in QUERIES)
    assert all('namespace="shop"' in query and auth == "Bearer private" for query, auth in seen)


def test_failed_query_stays_nan_and_records_failure():
    def respond(req):
        if "container_cpu_usage" in req.url.params["query"]:
            return httpx.Response(500)
        return httpx.Response(200, json={"status": "success", "data": {"result": []}})
    source = KubernetesProm("http://prom", "shop", client=httpx.Client(
        base_url="http://prom", transport=httpx.MockTransport(respond)))
    frame = source.signals("frontend", seconds=4, end=1000.0)
    assert frame.attrs["failed_queries"] == ["cpu_cores"]
    assert np.isnan(frame["cpu_cores"]).all()
    assert source.failures[-1][2] == "HTTPStatusError"
