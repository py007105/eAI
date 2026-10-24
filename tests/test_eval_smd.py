"""models/eval_smd.py on small synthetic data written here (no SMD file is read)."""
import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

spec = importlib.util.spec_from_file_location("eval_smd", Path(__file__).resolve().parents[1] / "models" / "eval_smd.py")
ev = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ev)


# ---------------------------------------------------------------- label runs
def test_label_runs_maximal_and_inclusive():
    assert ev.label_runs([0, 1, 1, 0, 0, 1, 0, 1, 1, 1]) == [(1, 2), (5, 5), (7, 9)]


def test_label_runs_edges_and_empty():
    assert ev.label_runs([1, 1, 0]) == [(0, 1)]
    assert ev.label_runs([0, 0, 0]) == []
    assert ev.label_runs([]) == []
    assert ev.label_runs([1]) == [(0, 0)]


# ---------------------------------------------------------------- at least k metrics
def test_machine_alarm_at_least_k():
    mf = np.array([[0, 0, 0], [1, 0, 0], [1, 1, 0], [1, 1, 1]], dtype=bool)
    assert ev.machine_alarm(mf, 1) == [False, True, True, True]
    assert ev.machine_alarm(mf, 2) == [False, False, True, True]
    assert ev.machine_alarm(mf, 3) == [False, False, False, True]


# ---------------------------------------------------------------- train-only parameters
def test_train_params_rules():
    rng = np.random.default_rng(0)
    train = np.column_stack([rng.normal(0.5, 0.1, 500), np.zeros(500), np.full(500, 0.2)])
    p = ev.train_params(train)
    assert p[0]["floor"] == pytest.approx(max(ev.nab.robust_scale(train[:, 0]), 0.01))
    assert p[0]["min_gap"] == pytest.approx(3 * p[0]["floor"])
    assert p[1]["floor"] == 0.01 and p[1]["min_gap"] == pytest.approx(0.03)      # constant metric: floor raised
    assert p[1]["T"] == pytest.approx(0.01)                                       # max 0 -> 0 + 0.01
    assert p[2]["T"] == pytest.approx(0.22)                                       # 0.2 + max(0.02, 0.01)
    big = np.full((10, 1), 5.0)
    assert ev.train_params(big)[0]["T"] == pytest.approx(5.5)                     # 5 + 0.1 * 5


def test_parameters_use_train_only():
    rng = np.random.default_rng(1)
    train = rng.normal(0.3, 0.05, (300, 2))
    test_a = rng.normal(0.3, 0.05, (100, 2))
    test_b = test_a.copy()
    test_b[50:60] = 9.0                                         # a very different test set
    assert ev.train_params(train) == ev.train_params(train)     # deterministic
    pa, pb = ev.train_params(train), ev.train_params(train)
    # thresholds are a function of train alone, so flags differ only where the test values differ
    fa, fb = ev.ft_metric_flags(test_a, pa, 1), ev.ft_metric_flags(test_b, pb, 1)
    assert not fa[50:60].any() and fb[50:60].all()
    assert (fa[:50] == fb[:50]).all() and (fa[60:] == fb[60:]).all()


def test_z_priming_scores_from_first_test_row():
    rng = np.random.default_rng(2)
    train = rng.normal(0.5, 0.01, (400, 1))
    test = np.full((10, 1), 0.5)
    test[0:3, 0] = 0.9                                          # a jump at the very start of test
    p = ev.train_params(train)
    zf = ev.z_metric_flags(train, test, p)
    # primed from train, so test row 0 is already scored: hot on rows 0-2, anomalous on the 3rd hot row
    assert zf[:, 0].tolist() == [False, False, True] + [False] * 7


# ---------------------------------------------------------------- interpretation labels
def test_parse_interpretation():
    text = "15849-16368:1,9,10,12\n16963-17517:1,2\n\n"
    assert ev.parse_interpretation(text) == [(15849, 16368, frozenset({1, 9, 10, 12})), (16963, 17517, frozenset({1, 2}))]


def test_explanation_score():
    n = 40
    events = [(10, 15), (25, 30)]
    mf = np.zeros((n, 3), dtype=bool)
    mf[11, 1] = True                    # metric 2 alarms first inside event 1
    mf[26, 0] = True                    # metric 1 alarms first inside event 2
    flags = ev.machine_alarm(mf, 1)
    interp = [(10, 15, frozenset({2, 3})), (24, 31, frozenset({3}))]
    e = ev.explanation(flags, mf, events, interp)
    assert e == {"hits": 1, "with_list": 2, "without_list": 0}
    e2 = ev.explanation(flags, mf, events, [(10, 15, frozenset({2}))])
    assert e2 == {"hits": 1, "with_list": 1, "without_list": 1}


# ---------------------------------------------------------------- scoring: no point adjustment
def test_no_point_adjustment():
    n = 100
    events = [(20, 39), (60, 69)]
    flags = [False] * n
    for i in range(25, 39):             # many alarm points inside event 1: one alarm event, one detection
        flags[i] = True
    for i in range(55, 62):             # alarm run that starts BEFORE event 2: not a detection of it
        flags[i] = True
    flags[80] = True                    # an isolated false alarm
    r = ev.score_rows(flags, events)
    assert r["events"] == 2 and r["detected"] == 1
    assert r["alarm_events"] == 3 and r["true_events"] == 1 and r["false_events"] == 2
    assert r["delays_min"] == [5.0]     # rows 25 - 20, 1 row = 1 minute
    assert r["outside_days"] == pytest.approx((n - 30) / 1440)
    d = ev.derived(ev.summarise([r]))
    assert d["recall"] == pytest.approx(0.5) and d["precision"] == pytest.approx(1 / 3)


def test_zero_denominator_is_na():
    r = ev.score_rows([False] * 10, [])
    d = ev.derived(ev.summarise([r]))
    assert d["recall"] is None and d["precision"] is None


# ---------------------------------------------------------------- end to end on a tiny synthetic machine
def _machine(tmp: Path, m: str):
    rng = np.random.default_rng(3)
    train = rng.normal(0.5, 0.02, (300, 38))
    test = rng.normal(0.5, 0.02, (200, 38))
    test[100:120, 4] = 0.95
    labels = np.zeros(200, dtype=int)
    labels[100:120] = 1
    for d in ev.FOLDERS:
        (tmp / d).mkdir(parents=True, exist_ok=True)
    np.savetxt(tmp / "train" / f"{m}.txt", train, delimiter=",", fmt="%.6f")
    np.savetxt(tmp / "test" / f"{m}.txt", test, delimiter=",", fmt="%.6f")
    np.savetxt(tmp / "test_label" / f"{m}.txt", labels, fmt="%d")
    (tmp / "interpretation_label" / f"{m}.txt").write_text("100-119:5\n", encoding="utf-8")


def test_evaluate_machine_end_to_end(tmp_path):
    _machine(tmp_path, "machine-1-1")
    r = ev.evaluate_machine(*ev.load_machine(tmp_path, "machine-1-1"))
    assert r["events"] == 1 and r["test_rows"] == 200
    for det in ("Z", "FT"):
        assert r["scores"][det]["detected"] == 1
        assert r["expl"][det] == {"hits": 1, "with_list": 1, "without_list": 0}


def test_label_length_mismatch_stops(tmp_path):
    _machine(tmp_path, "machine-1-1")
    train, test, labels, interp = ev.load_machine(tmp_path, "machine-1-1")
    with pytest.raises(SystemExit):
        ev.evaluate_machine(train, test, labels[:-1], interp)


# ---------------------------------------------------------------- refusing to run
def test_refuses_without_manifest(tmp_path):
    with pytest.raises(SystemExit, match="MANIFEST"):
        ev.main(["--smd", str(tmp_path), "--out", str(tmp_path / "out.md")])
    assert not (tmp_path / "out.md").exists()


def test_refuses_wrong_commit_or_hash(tmp_path):
    (tmp_path / "MANIFEST.json").write_text(json.dumps({"commit": "0" * 40, "files": []}), encoding="utf-8")
    with pytest.raises(SystemExit, match="pre-registered"):
        ev.check_inputs(tmp_path)
    _machine(tmp_path, "machine-1-1")
    (tmp_path / "MANIFEST.json").write_text(json.dumps({"commit": ev.SMD_COMMIT, "files": [
        {"path": "train/machine-1-1.txt", "sha256": "bad"}]}), encoding="utf-8")
    with pytest.raises(SystemExit, match="SHA256|missing"):
        ev.check_inputs(tmp_path)
