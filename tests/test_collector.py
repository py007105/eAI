"""Telemetry robustness: one failed Prometheus query marks that signal missing (NaN) and is recorded, instead of raising and
losing the whole tick. A failed `up` query is not mistaken for a service that is down. No Prometheus: httpx MockTransport."""
import httpx
import numpy as np

from eternalai import config
from eternalai.collector import Q, Prom
from eternalai.engine import Engine


def prom_with(fail_on=(), mode="http500"):
    """A fake Prometheus: every range query returns a flat series of 1.0, except queries containing a `fail_on` substring."""
    def handler(req: httpx.Request):
        q = req.url.params.get("query", "")
        if any(f in q for f in fail_on):
            if mode == "http500":
                return httpx.Response(500, text="boom")
            if mode == "error_status":
                return httpx.Response(200, json={"status": "error", "errorType": "bad_data"})
            if mode == "malformed":
                return httpx.Response(200, text="not json")
            raise httpx.ConnectError("refused", request=req)
        if req.url.path.endswith("query_range"):
            start, end = float(req.url.params["start"]), float(req.url.params["end"])
            values = [[t, "1"] for t in np.arange(start, end, 2.0)]
            return httpx.Response(200, json={"status": "success", "data": {"result": [{"values": values}]}})
        return httpx.Response(200, json={"status": "success", "data": {"result": [{"value": [0, "1"]}]}})
    p = Prom.__new__(Prom)
    p.c = httpx.Client(base_url="http://prom", transport=httpx.MockTransport(handler))
    p.failures = []
    return p


def test_one_failed_query_marks_only_that_signal_missing():
    for mode in ("http500", "error_status", "malformed", "connect"):
        p = prom_with(fail_on=["process_cpu_seconds_total"], mode=mode)
        df = p.signals("web", 60, end=1_000_000.0)
        assert df.attrs["failed_queries"] == ["cpu_cores"], mode
        assert df["cpu_cores"].isna().all() and df["mem_bytes"].notna().any() and df["up"].notna().any(), mode
        assert p.failures and p.failures[-1][2] in ("HTTPStatusError", "ValueError", "JSONDecodeError", "ConnectError"), mode


def test_a_failed_rate_query_stays_missing_and_is_not_turned_into_zero_traffic():
    p = prom_with(fail_on=['status=~"5.."'])
    df = p.signals("web", 60, end=1_000_000.0)
    assert "err_rate" in df.attrs["failed_queries"] and df["err_rate"].isna().all()   # not filled with 0.0 although up == 1


def test_instant_returns_nan_on_failure_and_records_it():
    p = prom_with(fail_on=["dependency_calls_total"])
    assert np.isnan(p.instant('sum(rate(dependency_calls_total{service="web"}[10s]))'))
    assert p.instant('up{job="app"}') == 1.0 and len(p.failures) == 1


def test_every_query_failing_raises_nothing():
    p = prom_with(fail_on=[""], mode="connect")           # "" matches every query: Prometheus unreachable
    df = p.signals("orders", 60, end=1_000_000.0)
    assert set(df.attrs["failed_queries"]) >= set(Q) and df.isna().all().all()


class _State:
    running, image_tag = True, "v1"


class _DV:
    def poll(self):
        return {s: _State() for s in config.SERVICES}


class _Quiet:
    threshold, limits = 1.0, {}

    def score(self, f):
        return 0.0

    def anomalous(self, f):
        return False


class _Grace:
    def in_grace(self, *a):
        return False


def observing_engine(prom):
    e = Engine.__new__(Engine)
    e.prom, e.dv, e.baselines, e.window_s, e.latest, e.grace = prom, _DV(), {}, 10.0, {}, _Grace()
    e.detectors = {s: _Quiet() for s in config.SERVICES}
    return e


def test_a_failed_up_query_does_not_make_a_running_service_look_down():
    e = observing_engine(prom_with(fail_on=["up{"]))
    feats, scores, anom = e._observe()
    assert anom == {s: False for s in config.SERVICES}
    assert all("up" in q for q in e.telemetry_failed.values()) and set(e.telemetry_failed) == set(config.SERVICES)


def test_a_real_up_zero_still_means_down():
    def handler(req):
        q = req.url.params.get("query", "")
        start, end = float(req.url.params.get("start", 0)), float(req.url.params.get("end", 10))
        val = "0" if q.startswith("up{") else "1"
        return httpx.Response(200, json={"status": "success", "data": {"result": [
            {"values": [[t, val] for t in np.arange(start, end, 2.0)]}]}})
    p = Prom.__new__(Prom)
    p.c, p.failures = httpx.Client(base_url="http://prom", transport=httpx.MockTransport(handler)), []
    e = observing_engine(p)
    _, _, anom = e._observe()
    assert all(anom.values()) and e.telemetry_failed == {}
