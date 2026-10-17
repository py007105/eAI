import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "dashboard"))
import views  # noqa: E402
from labels import LABELS, t  # noqa: E402

TOPO = {"web": ["orders", "inventory"], "orders": ["inventory", "payments"], "inventory": [], "payments": []}
SVC = {"web": {"anomalous": True, "features": {"up_frac": 1.0}, "state": {"running": True}},
       "orders": {"anomalous": True, "features": {}, "state": {"running": True}},
       "inventory": {"anomalous": True, "features": {"up_frac": 0.0}, "state": {"running": False}},
       "payments": {"anomalous": False, "features": {}, "state": {"running": True}}}
INC = {"id": "a", "opened_t": 100.0, "kind": "predicted", "status": "recovered", "abstained": False, "confidence": 0.9,
       "ranking": [{"service": "inventory", "score": 0.7}, {"service": "orders", "score": 0.2}],
       "report": {"summary": "inventory leaking", "likely_cause": "memory_leak", "runbook_id": "recreate_container",
                  "missing_information": []},
       "report_meta": {"provider": "template"}, "timeline": [{"t": 101.0, "msg": "x"}],
       "evidence": [{"id": "ev1", "summary": "mem rising"}],
       "forecasts": [{"resource": "memory", "share_of_limit_now": 0.4, "eta_s": 60, "eta_earliest_s": 40, "eta_latest_s": 90,
                      "slope_per_min": 1e8}],
       "verification": {"outcome": "recovered", "success_rate": 1.0, "probes": 20, "p_max_latency_s": 0.1},
       "before": {"checkout_success": 0.0, "error_ratio": 0.6, "p95_s": 1.4}, "after": {"error_ratio": 0.0, "p95_s": 0.05}}


def test_node_states_and_failing_path_highlight():
    assert [views.node_state(SVC[s]) for s in TOPO] == ["anomalous", "anomalous", "down", "healthy"]
    fig = views.service_map(SVC, TOPO)
    widths = [tr.line.width for tr in fig.data if tr.mode == "lines"]
    assert 5 in widths and 2 in widths  # a failing path is thicker than a healthy one


def test_panels_render_with_and_without_incident():
    for inc in (INC, None):
        views.causes_fig(inc), views.timeline(inc), views.evidence(inc), views.report(inc), views.proof(inc)
    fig, has = views.forecast_fig(INC)
    assert has and views.forecast_fig(None)[1] is False


def test_proof_banner_only_on_verified_recovery():
    ok_children, cls = views.proof(INC)
    assert cls == "ok"
    bad = {**INC, "verification": {**INC["verification"], "outcome": "unresolved", "success_rate": 0.0}}
    assert views.proof(bad)[1] == "bad"


def test_probability_shown_only_when_calibration_verified():
    hidden = str(views.report(INC, "en", show_prob=False))
    shown = str(views.report(INC, "en", show_prob=True))
    assert "90%" not in hidden and t("prob_hidden") in hidden       # default: no percentage without a calibration check
    assert "90%" in shown and t("prob_hidden") not in shown


def test_labels_fallback_and_hindi_present():
    assert t("panel_map", "hi") != t("panel_map", "en")
    assert t("axis_support", "hi") == LABELS["en"]["axis_support"]  # untranslated key falls back to English


def test_every_label_key_used_in_code_exists():
    """Regression: a panel once showed the raw key 'PANEL_SCORE' because the key did not exist."""
    import re
    root = Path(__file__).resolve().parents[1] / "dashboard"
    used = set()
    for f in ("views.py", "app.py"):
        src = (root / f).read_text(encoding="utf-8")
        used |= set(re.findall(r"""\bt\(\s*["']([a-z0-9_\-]+)["']""", src))
        used |= set(re.findall(r"""P\([^)]*?,\s*["'](panel_[a-z]+)["']""", src))
        used |= set(re.findall(r"""cell\(\s*["']([a-z_]+)["']""", src))
    used |= {f"kind_{k}" for k in ("reactive", "predicted")} | {f"mode_{m}" for m in ("watch-only", "ask-first", "autopilot")}
    missing = sorted(k for k in used if k not in LABELS["en"])
    assert not missing, f"label keys used but not defined: {missing}"


def test_incident_without_verification_is_not_shown_as_all_quiet_or_recovered():
    waiting = {**INC, "status": "awaiting_approval", "verification": None}
    children, cls = views.proof(waiting)
    assert cls == "" and t("not_verified") in str(children) and t("no_incident") not in str(children)


def test_empty_charts_show_a_message_not_bare_axes():
    fig, has = views.forecast_fig(None)
    assert not has and fig.layout.annotations and fig.layout.xaxis.visible is False
    assert views.causes_fig(None).layout.annotations
