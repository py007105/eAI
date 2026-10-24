import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "dashboard"))
from charts import History, incident_stats, service_figure  # noqa: E402

SAMPLES_DIR = Path(__file__).resolve().parents[1] / "dashboard" / "preview"
SERVICES = json.loads((SAMPLES_DIR / "sample_services.json").read_text(encoding="utf-8"))
INCIDENTS = json.loads((SAMPLES_DIR / "sample_incidents.json").read_text(encoding="utf-8"))


def _history(n_ticks=None, max_points=300):
    h = History(max_points=max_points)
    ticks = SERVICES["ticks"][:n_ticks] if n_ticks is not None else SERVICES["ticks"]
    for tick in ticks:
        h.add(tick)
    return h


def test_history_keeps_only_the_last_max_points():
    h = History(max_points=5)
    for tick in SERVICES["ticks"][:8]:
        h.add(tick)
    assert len(h.ticks) == 5
    assert [t for t, _ in h.ticks] == [t * 2 for t in (3, 4, 5, 6, 7)]


def test_payments_series_has_gap_at_ticks_10_to_12():
    h = _history(n_ticks=20)
    ts, vals = h.series("payments", "lat_ratio")
    gap = {t: v for t, v in zip(ts, vals) if v is None}
    assert set(gap) == {20, 22, 24}  # tick indices 10, 11, 12 -> t = 20, 22, 24
    assert vals[9] == 1.0 and vals[13] == 1.0  # ticks just outside the gap are present


def test_service_figure_has_one_trace_per_present_feature_and_uses_eternal_template():
    h = _history()
    fig = service_figure(h, "inventory", "en")
    assert len(fig.data) == 4  # lat_ratio, error_ratio, mem_share, rps_ratio all present throughout
    assert fig.layout.template.layout.paper_bgcolor == "rgba(0,0,0,0)"  # identifies the "eternal" template


def test_unknown_service_gives_the_empty_figure():
    h = _history()
    fig = service_figure(h, "does-not-exist", "en")
    assert fig.layout.annotations
    assert fig.layout.xaxis.visible is False
    assert not fig.data


def test_empty_history_gives_the_empty_figure():
    h = History()
    fig = service_figure(h, "inventory", "en")
    assert fig.layout.annotations
    assert not fig.data


def test_incident_stats_matches_expected_numbers():
    stats = incident_stats(INCIDENTS["incidents"])
    assert stats["detect_to_action"] == {"n": 2, "median": 9.0, "min": 6, "max": 12}
    assert stats["action_to_verified"] == {"n": 2, "median": 25.5, "min": 23, "max": 28}
    assert stats["by_status"] == {"recovered": 2, "escalated": 1, "awaiting_approval": 1}
    assert stats["not_executed"] == 2


def test_incident_stats_on_empty_list():
    stats = incident_stats([])
    assert stats["detect_to_action"] is None
    assert stats["action_to_verified"] is None
    assert stats["by_status"] == {}
    assert stats["not_executed"] == 0
