import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("hw", Path(__file__).resolve().parents[1] / "scripts" / "health_watch.py")
hw = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hw)


def rec(state="running", health="none", restarts=0):
    return {"container": "eai-x-1", "state": state, "health": health, "restarts": restarts, "started": "t"}


def snap(**over):
    s = {k: rec() for k in hw.REQUIRED}
    s.update(over)
    return s


def test_parse_line():
    r = hw.parse_line("/eai-web-1|running|none|2|2026-10-18T11:34:08Z")
    assert r == {"container": "eai-web-1", "state": "running", "health": "none", "restarts": 2, "started": "2026-10-18T11:34:08Z"}


def test_new_started_at_is_not_an_alert_but_restart_count_rise_is():
    j = hw.Judge()
    assert j.step(snap()) == []
    assert j.step(snap(web=dict(rec(), started="newer"))) == []          # runbook recreation
    al = j.step(snap(web=rec(restarts=1)))
    assert len(al) == 1 and "RestartCount rose 0 -> 1" in al[0]


def test_down_needs_three_consecutive_samples_and_missing_counts_as_down():
    j = hw.Judge()
    assert j.step(snap(orders=rec("restarting"))) == [] and j.step(snap(orders=None)) == []
    al = j.step(snap(orders=rec("exited")))
    assert len(al) == 1 and "orders not running" in al[0]
    assert j.step(snap(orders=rec())) == [] and j.step(snap(orders=rec("exited"))) == []      # reset by a good sample


def test_unhealthy_three_in_a_row():
    j = hw.Judge()
    assert j.step(snap(web=rec(health="unhealthy"))) == [] and j.step(snap(web=rec(health="unhealthy"))) == []
    assert "unhealthy" in j.step(snap(web=rec(health="unhealthy")))[0]


def test_window_flags_only_inside_window_and_only_bad_lines():
    lines = ["100\tt\tweb\teai-web-1\trunning\tnone\t0\ts\n", "200\tt\tweb\teai-web-1\texited\tnone\t0\ts\n",
             "210\tt\tALERT\tx\n", "300\tt\tweb\teai-web-1\trunning\tunhealthy\t0\ts\n", "500\tt\tweb\teai-web-1\texited\tnone\t0\ts\n",
             "50\tt\tWATCHER_START\tinterval 60s\n"]
    got = hw.window_flags(lines, 150, 400)
    assert len(got) == 3 and all(x.split("\t")[0] in ("200", "210", "300") for x in got)
