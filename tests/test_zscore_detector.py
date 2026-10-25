"""engine.zscore_detector: equals the benchmark port, and follows the plan's rule (§6.3, §9.1)."""
import math

import numpy as np
import pytest

from engine import baselines as port                     # read-only: the frozen benchmark port
from engine.zscore_detector import (BASELINE_WINDOW, STREAK_NEEDED, WARMUP_POINTS, Z_LIMIT, SignalConfig,
                                       ZResult, ZScoreDetector)

PORT_CONFIGS = {m: SignalConfig(c["floor"], c["min_gap"], "upper") for m, c in port.ZSCORE_METRICS.items()}
# level, noise and fault size per metric, so each series has quiet stretches, spikes and sustained faults
SCALE = {"p95": (60.0, 8.0, 250.0), "err": (0.01, 0.004, 0.4), "cpu": (20.0, 4.0, 70.0), "mem": (120.0, 3.0, 150.0)}


def series(metric, seed, n=400):
    rng = np.random.default_rng(seed)
    level, noise, fault = SCALE[metric]
    x = level + rng.normal(0, noise, n)
    for _ in range(4):                                       # sustained faults of random length
        s = int(rng.integers(20, n - 30))
        x[s:s + int(rng.integers(2, 25))] += fault * rng.uniform(0.3, 1.2)
    for i in rng.choice(n, 12, replace=False):               # single spikes
        x[i] += fault * rng.uniform(-0.5, 1.0)
    vals = [float(v) for v in x]
    for i in rng.choice(n, 10, replace=False):               # missing values
        vals[i] = None if i % 2 else float("nan")
    return vals


def same(a, b):
    return (a is None and b is None) or (a is not None and b is not None and a == b)


# (a) equals the port
@pytest.mark.parametrize("metric", sorted(port.ZSCORE_METRICS))
@pytest.mark.parametrize("seed", [1, 2, 3, 4])
def test_equals_baseline_port(metric, seed):
    assert (Z_LIMIT, STREAK_NEEDED, WARMUP_POINTS) == (port.Z_LIMIT, port.STREAK_NEEDED, port.WARMUP_POINTS)
    old, new = port.ZScoreDetector(), ZScoreDetector(PORT_CONFIGS)
    n_anom = n_hot = 0
    for v in series(metric, seed):
        a, b = old.update("svc", metric, v), new.update(("svc", metric), v)
        assert a["z"] == b.z and a["hot"] == b.hot and a["anomalous"] == b.anomalous and same(a["mean"], b.mean)
        n_hot += b.hot
        n_anom += b.anomalous
    assert n_hot > 0 and n_anom > 0                           # the comparison exercised the alarm path
    assert len(old.baseline[("svc", metric)]) == new.explain(("svc", metric))["n_baseline"]


def test_baseline_window_matches_port():
    assert BASELINE_WINDOW == 120
    old = port.ZScoreDetector()
    old.update("s", "cpu", 1.0)
    assert old.baseline[("s", "cpu")].maxlen == BASELINE_WINDOW


# (b) warm-up
def test_warmup_never_anomalous():
    d = ZScoreDetector(default=SignalConfig(1.0, 0.0))
    for i in range(WARMUP_POINTS):
        r = d.update("k", 1000.0 * (i % 2))                  # wild values, still never anomalous
        assert r == ZResult(0.0, False, False, None, None, i + 1)
    r = d.update("k", 10_000.0)
    assert r.mean is not None and r.hot


# (c) a sustained fault is never absorbed
def test_sustained_fault_not_absorbed():
    d = ZScoreDetector(default=SignalConfig(1.0, 5.0))
    rng = np.random.default_rng(0)
    for v in 50 + rng.normal(0, 1, 40):
        d.update("k", v)
    n_before = d.explain("k")["n_baseline"]
    results = [d.update("k", 200.0) for _ in range(500)]
    assert all(r.hot for r in results) and all(r.anomalous for r in results[STREAK_NEEDED - 1:])
    assert all(r.n_baseline == n_before for r in results)          # nothing absorbed
    assert results[-1].mean == results[0].mean and results[-1].std == results[0].std


# (d) streak of 3
def test_three_in_a_row():
    d = ZScoreDetector(default=SignalConfig(1.0, 0.0))
    for _ in range(20):
        d.update("k", 10.0)
    flags = [d.update("k", v).anomalous for v in [100, 100, 10, 100, 100, 100, 100, 10, 100]]
    assert flags == [False, False, False, False, False, True, True, False, False]


# (e) min_gap blocks a big z with a tiny absolute gap
def test_min_gap_blocks_tiny_gap():
    d = ZScoreDetector(default=SignalConfig(0.001, 1.0))
    for _ in range(20):
        d.update("k", 10.0)
    r = d.update("k", 10.5)                                   # z = 500, gap = 0.5 < 1.0
    assert r.z > 100 and not r.hot
    assert d.update("k", 11.5).hot                            # gap 1.5 > 1.0


# (f) directions
@pytest.mark.parametrize("direction,up,down", [("upper", True, False), ("lower", False, True),
                                               ("two_sided", True, True)])
def test_directions(direction, up, down):
    d = ZScoreDetector(default=SignalConfig(1.0, 2.0, direction))
    for _ in range(20):
        d.update("k", 50.0)
    assert d.update("k", 80.0).hot is up
    assert d.update("k", 20.0).hot is down
    assert d.update("k", 51.0).hot is False                   # inside the band either way


def test_lower_streak_and_explain():
    d = ZScoreDetector(default=SignalConfig(1.0, 2.0, "lower"))
    for _ in range(20):
        d.update("k", 50.0, t=0)
    for i in range(3):
        r = d.update("k", 5.0, t=i + 1)
    assert r.anomalous and r.z < -Z_LIMIT
    e = d.explain("k")
    assert e["direction"] == "lower" and e["side"] == "below" and e["value"] == 5.0 and e["mean"] == 50.0
    assert e["t"] == 3 and e["anomalous"] and not e["warming_up"]


def test_bad_direction_rejected():
    with pytest.raises(ValueError):
        SignalConfig(1.0, 1.0, "sideways")


# (g) missing values
@pytest.mark.parametrize("bad", [None, float("nan"), float("inf"), "x"])
def test_missing_values_change_nothing(bad):
    d = ZScoreDetector(default=SignalConfig(1.0, 0.0))
    for _ in range(20):
        d.update("k", 10.0)
    d.update("k", 100.0); d.update("k", 100.0)               # streak 2
    before = (list(d._base["k"]), d._streak["k"], dict(d._last["k"]))
    r = d.update("k", bad)
    assert r.z == 0.0 and not r.hot and not r.anomalous and r.mean is None
    assert (list(d._base["k"]), d._streak["k"], dict(d._last["k"])) == before
    assert d.update("k", 100.0).anomalous                     # streak continued: 3 in a row
    d2 = ZScoreDetector(default=SignalConfig(1.0, 0.0))
    d2.update("new", bad)
    assert d2.explain("new") is None and "new" not in d2._base


# per-key state
def test_state_is_per_key():
    d = ZScoreDetector({"cpu": SignalConfig(1.0, 0.0), "mem": SignalConfig(1.0, 0.0)})
    for _ in range(20):
        d.update(("a", "cpu"), 10.0); d.update(("b", "cpu"), 10.0)
    for _ in range(3):
        ra = d.update(("a", "cpu"), 100.0)
        rb = d.update(("b", "cpu"), 10.0)
    assert ra.anomalous and not rb.anomalous
    assert d.update(("a", "mem"), 100.0).mean is None          # a new key starts its own warm-up
    with pytest.raises(KeyError):
        d.update(("a", "disk"), 1.0)


# (h) deterministic
def test_deterministic():
    vals = series("p95", 7)
    run = lambda: [d.update(("s", "p95"), v) for d in [ZScoreDetector(PORT_CONFIGS)] for v in vals]
    a, b = run(), run()
    assert all((x.z == y.z or (math.isnan(x.z) and math.isnan(y.z))) and x == y for x, y in zip(a, b))
