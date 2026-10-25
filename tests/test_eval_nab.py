"""ml/models/eval_nab.py event scoring on small synthetic series written here (no NAB data is read)."""
import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

spec = importlib.util.spec_from_file_location("eval_nab", Path(__file__).resolve().parents[1] / "ml" / "models" / "eval_nab.py")
ev = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ev)

T0 = pd.Timestamp("2020-01-01 00:00:00")


def ts(n, step_min=5):
    return [T0 + pd.Timedelta(minutes=step_min * i) for i in range(n)]


def at(i, step_min=5):
    return T0 + pd.Timedelta(minutes=step_min * i)


def flags(n, on):
    f = [False] * n
    for i in on:
        f[i] = True
    return f


def test_consecutive_alarm_points_merge_into_one_event():
    f = flags(30, [10, 11, 12, 13, 20, 22, 23])
    assert ev.alarm_event_starts(f, 0) == [10, 20, 22]
    r = ev.score(ts(30), f, 0, [])
    assert r["alarm_events"] == 3 and r["false_events"] == 3


def test_probationary_alarms_not_scored_and_crossing_run_starts_at_first_scored_row():
    f = flags(30, [2, 3, 8, 9, 10, 11, 15])
    assert ev.alarm_event_starts(f, 10) == [10, 15]


def test_in_window_and_out_of_window_rule():
    t = ts(100)
    windows = [(at(20), at(30)), (at(60), at(70))]
    f = flags(100, [25, 26, 40, 45, 70])                        # 25-26 in w1, 40 and 45 outside, 70 on w2's end
    r = ev.score(t, f, 0, windows)
    assert (r["detected"], r["evaluable"]) == (2, 2)
    assert (r["true_events"], r["false_events"], r["alarm_events"]) == (2, 2, 4)
    assert ev.derived(r)["precision"] == 0.5 and ev.derived(r)["recall"] == 1.0


def test_event_starting_before_window_does_not_detect_it():
    t = ts(60)
    windows = [(at(20), at(30))]
    f = flags(60, range(15, 28))                               # one event from row 15 to 27, starts before the window
    r = ev.score(t, f, 0, windows)
    assert r["detected"] == 0 and r["true_events"] == 0 and r["false_events"] == 1
    assert ev.derived(r)["recall"] == 0.0


def test_delay_is_first_event_start_minus_window_start():
    t = ts(100)
    windows = [(at(20), at(40)), (at(60), at(80))]
    f = flags(100, [23, 24, 30, 75])
    r = ev.score(t, f, 0, windows)
    assert r["delays_min"] == [15.0, 75.0]                     # (23-20)*5 and (75-60)*5 minutes
    d = ev.derived(r)
    assert (d["delay_med"], d["delay_min"], d["delay_max"]) == (45.0, 15.0, 75.0)


def test_no_point_adjustment():
    """One alarm point in a long window: the window counts once; points and events are not relabelled or inflated."""
    t = ts(200)
    windows = [(at(50), at(150))]
    one = ev.score(t, flags(200, [100]), 0, windows)
    many = ev.score(t, flags(200, [60, 62, 64, 66, 68]), 0, windows)
    assert one["detected"] == many["detected"] == 1
    assert one["true_events"] == 1 and many["true_events"] == 5      # events, not the window's 101 points
    assert ev.derived(one)["recall"] == ev.derived(many)["recall"] == 1.0
    # precision depends only on alarm events, never on how many points of the window were labelled
    r = ev.score(t, flags(200, [100, 10, 180]), 0, windows)
    assert (r["true_events"], r["false_events"]) == (1, 2) and ev.derived(r)["precision"] == pytest.approx(1 / 3)


def test_excluded_windows_and_outside_days():
    t = ts(1000)                                                # 5-minute steps
    windows = [(at(50), at(80)), (at(300), at(339))]             # first starts before the scored period (row 150)
    f = flags(1000, [60, 160, 310, 500])
    r = ev.score(t, f, 150, windows)
    assert (r["evaluable"], r["excluded"], r["detected"]) == (1, 1, 1)
    assert (r["true_events"], r["false_events"], r["excluded_events"]) == (1, 2, 0)
    assert r["outside_days"] == pytest.approx((850 - 40) * 5 / 1440)
    assert ev.derived(r)["per_day"] == pytest.approx(2 / ((850 - 40) * 5 / 1440))


def test_zero_denominators_are_na():
    d = ev.derived(ev.score(ts(50), [False] * 50, 0, []))
    assert d["recall"] is None and d["precision"] is None and d["delay_med"] is None
    assert ev.fmt(d["recall"]) == "n/a"


def test_probation_len_follows_nab():
    assert ev.probation_len(4032) == 604 and ev.probation_len(5000) == 750 and ev.probation_len(20000) == 750


def test_parameter_rules():
    v = [10.0, 11.0, 12.0, 13.0, 14.0]
    s = 1.4826 * 1.0                                           # MAD of v is 1
    cfg = ev.zscore_config(v, "upper")
    assert cfg.floor == pytest.approx(s) and cfg.min_gap == pytest.approx(3 * s) and cfg.direction == "upper"
    assert ev.robust_scale([5.0, 5.0, 5.0, 9.0]) == pytest.approx(np.std([5.0, 5.0, 5.0, 9.0]))   # MAD 0 -> std
    assert ev.robust_scale([7.0, 7.0]) == pytest.approx(7e-6)                                     # std 0 -> tiny
    assert ev.ft_threshold(v, cpu=True) == 90.0
    q50, q99 = np.percentile(v, 50), np.percentile(v, 99)
    assert ev.ft_threshold(v, cpu=False) == pytest.approx(q99 + (q99 - q50))


def test_fixed_threshold_flags_and_streak():
    vals = [1, 95, 95, 1, 95, 95, 95, 95, None, 95]
    assert ev.ft_flags(vals, 90, 1) == [False, True, True, False, True, True, True, True, False, True]
    assert ev.ft_flags(vals, 90, 3) == [False] * 6 + [True, True, False, False]


def test_end_to_end_on_synthetic_files(tmp_path):
    """A tiny fake NAB folder: inputs are checked against MANIFEST.json and the report is written."""
    nab = tmp_path / "nab"
    rng = np.random.default_rng(0)
    raw_windows = {}
    for k, s in enumerate(ev.SERIES):
        n = 600
        t = ts(n)
        x = 50 + rng.normal(0, 1, n)
        x[400:410] += 60                                       # one big upward fault
        p = nab / ev.series_path(s)
        p.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame({"timestamp": [str(u) for u in t], "value": x}).to_csv(p, index=False)
        raw_windows[f"realAWSCloudwatch/{s}.csv"] = [[str(at(390)), str(at(420))]]
    (nab / "labels").mkdir(parents=True)
    (nab / ev.LABELS).write_text(json.dumps(raw_windows))
    files = [{"path": rel, "sha256": hashlib.sha256((nab / rel).read_bytes()).hexdigest()}
             for rel in [ev.series_path(s) for s in ev.SERIES] + [ev.LABELS]]
    (nab / "MANIFEST.json").write_text(json.dumps({"commit": ev.NAB_COMMIT, "files": files}))
    out = tmp_path / "report.md"
    assert ev.main(["--nab", str(nab), "--out", str(out)]) == 0
    text = out.read_text(encoding="utf-8")
    assert "not live verified" in text and "no point-adjustment" in text and files[0]["sha256"] in text
    assert "| all 17 series (17) | Z-up | 17 / 17 |" in text     # the fault is caught in every series
    # a changed input file is refused
    (nab / ev.series_path(ev.SERIES[0])).write_text("timestamp,value\n")
    with pytest.raises(SystemExit):
        ev.main(["--nab", str(nab), "--out", str(out)])
