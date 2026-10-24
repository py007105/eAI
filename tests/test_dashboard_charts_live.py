"""Mihir's chart components wired into the live dashboard: the poller feeds the history from /services, and the
charts callback reads only the poller's cache (live shapes from eternalai/api.py: /services and /incidents)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "dashboard"))

SERVICES = {"services": {"inventory": {"features": {"lat_ratio": 1.0, "rps_ratio": 1.0, "error_ratio": 0.0, "mem_share": 0.74,
                                                    "mem_slope_share_per_min": 0.38, "up_frac": 1.0},
                                       "score": 3.2, "anomalous": True, "state": {"running": True, "image_tag": "x"}},
                         "web": {"features": {"lat_ratio": 1.0, "rps_ratio": 1.0, "error_ratio": 0.0, "mem_share": 0.2,
                                              "up_frac": 1.0}, "score": 0.1, "anomalous": False, "state": None}},
            "topology": {}, "depfail": {}}
INCIDENTS = [{"id": "i1", "status": "recovered", "opened_t": 100.0,
              "actions": [{"executed": True, "executed_t": 108.0}], "verification": {"t": 130.0, "outcome": "recovered"}},
             {"id": "i2", "status": "awaiting_approval", "opened_t": 200.0, "actions": [{"executed": False}],
              "verification": None}]


def fake_get(cache):
    return lambda k, d=None: cache.get(k, d)


def test_poller_feeds_history_from_services_snapshots():
    import app as dash_app
    p = dash_app.Poller()
    p.record_services(SERVICES, 10.0)
    p.record_services(SERVICES, 11.0)
    ts, vals = p.history.series("inventory", "mem_share")
    assert ts == [10.0, 11.0] and vals == [0.74, 0.74]
    p.record_services(None, 12.0)                     # an empty answer adds a gap, not a crash
    assert p.history.series("inventory", "mem_share")[1][-1] is None


def test_charts_callback_uses_live_features_and_incidents(monkeypatch):
    import app as dash_app
    p = dash_app.Poller()
    for i in range(3):
        p.record_services(SERVICES, 100.0 + i)
    monkeypatch.setattr(dash_app, "poller", p)
    monkeypatch.setattr(p, "get", fake_get({"services": SERVICES, "incidents": INCIDENTS}))
    out = dash_app.charts_view(0, "en", "inventory")
    fig, explanation, stats = out[1], str(out[2]), str(out[5])
    assert len(fig.data) == 4                           # latency, traffic, errors, memory
    assert "74%" in explanation and "38%" in explanation
    assert "awaiting_approval" in stats and "recovered" in stats and "8.0" in stats and "22.0" in stats
    assert "Live" in out[3] and "Live" in out[6]
    hi = dash_app.charts_view(0, "hi", "inventory")
    assert "74%" in str(hi[2]) and str(hi[2]) != explanation


def test_charts_callback_without_backend_shows_no_chart(monkeypatch):
    import app as dash_app
    p = dash_app.Poller()
    p.record_services(SERVICES, 100.0)                  # old data is not shown once the backend is gone
    monkeypatch.setattr(dash_app, "poller", p)
    monkeypatch.setattr(p, "get", fake_get({}))
    out = dash_app.charts_view(0, "en", "inventory")
    assert len(out[1].data) == 0 and "No data yet" in str(out[1].layout.annotations)
    assert "Nothing to report" in str(out[2])
    assert "None" in str(out[5]) or "-" in str(out[5])   # empty statistics table, no invented numbers


def test_populated_explanation_check_needs_a_non_empty_match():
    """D6 of scripts/live_check_dashboard_charts.py: empty-versus-empty never counts; the sentences must equal
    explain_service() on API features sampled within 4 s of the page read."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("ldc", Path(__file__).resolve().parents[1] / "scripts" / "live_check_dashboard_charts.py")
    ldc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ldc)
    from explain_words import explain_service
    feats = SERVICES["services"]["inventory"]["features"]
    want = explain_service("inventory", feats, "en")
    assert want                                                            # the fixture is a populated case
    assert ldc.populated_match([(10.0, want)], [(12.0, feats)], "inventory") == (10.0, want)
    assert ldc.populated_match([(10.0, want)], [(20.0, feats)], "inventory") is None                  # too far apart
    assert ldc.populated_match([(10.0, [])], [(10.0, {"up_frac": 1.0})], "inventory") is None         # empty vs empty
    nothing = ["Nothing to report for this service at this tick."]
    assert ldc.populated_match([(10.0, nothing)], [(10.0, {"up_frac": 1.0})], "inventory") is None
    assert ldc.populated_match([(10.0, ["something else"])], [(10.0, feats)], "inventory") is None
