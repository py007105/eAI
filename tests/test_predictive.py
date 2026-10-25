"""Forecast warnings every tick: attached to an open incident (with their time), or opening a predicted incident when none
is active. Before 2026-10-21 the forecast ran only with no incident open, so it never warned live (docs/FORECAST_CHECK.md)."""
import numpy as np
import pandas as pd

from engine.engine import Engine, Incident
from tests.test_autopilot_path import make_engine

LIMIT = 268e6


def leak_frame(rate_bytes_per_s=3e6, start=80e6, seconds=60):
    t = np.arange(0, seconds, 2.0)
    return pd.DataFrame({"mem_bytes": start + rate_bytes_per_s * t, "mem_limit_bytes": LIMIT * np.ones_like(t),
                         "scratch_bytes": np.zeros_like(t)}, index=t)


def flat_frame():
    t = np.arange(0, 60, 2.0)
    return pd.DataFrame({"mem_bytes": 60e6 * np.ones_like(t), "mem_limit_bytes": LIMIT * np.ones_like(t),
                         "scratch_bytes": np.zeros_like(t)}, index=t)


def real_warnings(e, frames):
    """Run the real forecaster (not the test fake) on the given frames."""
    from engine.investigate import Investigator
    import engine.engine as eng
    e.frames = frames
    saved = eng.Investigator
    eng.Investigator = Investigator
    try:
        return Engine._forecast_warnings(e)
    finally:
        eng.Investigator = saved


def test_forecaster_warns_on_a_steady_leak_only(monkeypatch):
    e = make_engine("watch-only", "orders", "memory_leak", monkeypatch)
    w = real_warnings(e, {"web": flat_frame(), "orders": leak_frame(), "payments": flat_frame(), "inventory": flat_frame()})
    assert [(s, f["resource"]) for s, _, f in w] == [("orders", "memory")]
    assert w[0][2]["eta_earliest_s"] < 90
    assert real_warnings(e, {s: flat_frame() for s in ("web", "orders", "payments", "inventory")}) == []


def test_warning_attaches_to_the_open_incident_once(monkeypatch):
    e = make_engine("watch-only", "orders", "memory_leak", monkeypatch)
    inc = Incident("r1", 1000.0)
    inc.services = ["orders", "web"]
    e.incidents.append(inc)
    f = {"resource": "memory", "eta_earliest_s": 40.0, "eta_latest_s": 70.0, "share_of_limit_now": 0.5}
    monkeypatch.setattr(e, "_forecast_warnings", lambda: [("orders", None, f)])
    e._predictive({}, 1010.0)
    e._predictive({}, 1012.0)
    assert len(e.incidents) == 1 and len(inc.forecasts) == 1
    assert inc.forecasts[0]["t"] == 1010.0 and inc.forecasts[0]["service"] == "orders"
    assert any("forecast: orders memory exhaustion in 40-70s" in x["msg"] for x in inc.timeline)


def test_without_an_active_incident_a_predicted_incident_is_opened_and_goes_through_policy(monkeypatch):
    e = make_engine("autopilot", "orders", "memory_leak", monkeypatch)
    f = {"resource": "memory", "eta_earliest_s": 40.0, "eta_latest_s": 70.0, "share_of_limit_now": 0.5}
    monkeypatch.setattr(e, "_forecast_warnings", lambda: [("orders", None, f)])
    e._predictive({"orders": {}}, 2000.0)
    inc = e.incidents[-1]
    assert inc.kind == "predicted" and inc.forecasts[0]["t"] == 2000.0
    act = inc.actions[-1]                       # recreate on a stateful service is high risk: waits even in autopilot
    assert act["runbook_id"] == "recreate_container" and act["verdict"] == "needs_approval" and e.executor.calls == []


def test_no_warning_no_change(monkeypatch):
    e = make_engine("autopilot", "orders", "memory_leak", monkeypatch)
    monkeypatch.setattr(e, "_forecast_warnings", lambda: [])
    e._predictive({}, 1.0)
    assert e.incidents == []
