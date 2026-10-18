"""forecast_check analysis on SYNTHETIC runs only."""
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("fc", Path(__file__).resolve().parents[1] / "scripts" / "forecast_check.py")
fc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fc)
T0 = 1000.0
MB = 1024 * 1024


def run(scn, seed, warn_at=None, limit_at=None, executed=0, wrong=False, extra_incidents=(), start_changes_at=None):
    mem = [(T0 + i, (100 + i * 2) * MB) for i in range(-30, 120)]
    scratch = [(T0 + i, 10 * MB if scn == "disk_fill" else 0.0) for i in range(-30, 120)]
    if scn == "memory_leak" and limit_at:
        mem = [(t, (0.96 * 256 * MB if t >= T0 + limit_at else 50 * MB)) for t, _ in mem]
    if scn == "disk_fill" and limit_at:
        scratch = [(t, (300 * MB if t >= T0 + limit_at else 1 * MB)) for t, _ in scratch]
    start = [(T0 + i, 5.0 if (start_changes_at is None or i < start_changes_at) else 9.0) for i in range(-30, 120)]
    inc = list(extra_incidents)
    if warn_at is not None:
        inc.append({"id": "p", "kind": "predicted", "opened_t": T0 + warn_at, "services": ["orders" if not wrong else "web"],
                    "forecasts": [{"eta_earliest_s": 20, "eta_latest_s": 60}], "actions": [], "evidence": []})
    return {"scenario": scn, "seed": seed, "truth": {"t_inject": T0, "target": "orders"}, "score": {"t_end": T0 + 110}, "incidents": inc,
            "audit": [{"t": T0 + 5}] * executed, "prom": {"mem": mem, "mem_limit": [(T0, 256.0 * MB)], "scratch": scratch, "start": start}}


def test_lead_time_is_limit_minus_first_warning_and_censored_when_no_limit():
    a = fc.analyse_run(run("memory_leak", 1, warn_at=40, limit_at=90))
    assert a["warned"] and a["lead_s"] == 50.0 and a["limit_reached"] and a["actual_inside_window"] is True
    b = fc.analyse_run(run("disk_fill", 2, warn_at=30, limit_at=None))
    assert b["warned"] and b["lead_s"] is None and not b["limit_reached"]


def test_stated_window_containment():
    a = fc.analyse_run(run("disk_fill", 1, warn_at=40, limit_at=80))      # lead 40 inside [20, 60]
    assert a["lead_s"] == 40.0 and a["actual_inside_window"] is True


def test_restart_of_target_counts_as_limit():
    a = fc.analyse_run(run("memory_leak", 1, warn_at=20, limit_at=None, start_changes_at=70))
    assert a["lead_s"] == 50.0


def test_forecast_evidence_on_reactive_incidents_is_not_a_warning():
    reactive = {"id": "r", "kind": "reactive", "opened_t": T0 + 10, "services": ["orders"], "actions": [], "evidence": [{"tool": "forecast", "summary": "x"}]}
    a = fc.analyse_run(run("traffic_surge", 1, extra_incidents=[reactive]))
    assert not a["warned"] and a["predicted incidents"] == 0 and a["forecast_evidence_on_reactive"] == 1


def test_incidents_outside_the_run_window_are_ignored():
    old = {"id": "o", "kind": "predicted", "opened_t": T0 - 500, "services": ["orders"], "forecasts": [], "actions": [], "evidence": []}
    assert not fc.analyse_run(run("traffic_surge", 1, extra_incidents=[old]))["warned"]


def rows(good=True):
    out = []
    for sc in fc.GRADUAL:
        for s in range(5):
            out.append(fc.analyse_run(run(sc, s, warn_at=30 if (good or s < 2) else None, limit_at=90)))
    for sc in fc.HEALTHY:
        for s in range(5):
            out.append(fc.analyse_run(run(sc, s)))
    return out


def test_criteria_pass_on_a_good_set_and_fail_on_missed_warnings_and_actions():
    ok = fc.evaluate(rows(True))
    assert all(p for _, p, _ in ok)
    bad = fc.evaluate(rows(False))
    assert not dict((c, p) for c, p, _ in bad)["memory_leak: warning issued before the limit in at least 4 of 5 runs"]
    r = rows(True)
    r[0]["executed_actions"] = 1
    assert not dict((c, p) for c, p, _ in fc.evaluate(r))["watch-only: executed actions in every run"]


def test_healthy_run_with_a_predicted_incident_fails_the_criterion_and_wording_is_counts():
    r = rows(True)
    r.append(fc.analyse_run(run("good_deploy", 9, warn_at=10)))
    crit = fc.evaluate(r)
    row = next(x for x in crit if x[0].startswith("good_deploy"))
    assert row[1] is False and "warnings in" in row[2] and "no false" not in " ".join(c[2] for c in crit).lower()
    assert "FIXTURE" in fc.render(r, crit, fixture=True)
