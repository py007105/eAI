import numpy as np
import pandas as pd

from eternalai.features.window import FEATURE_NAMES, fit_baseline, window_features


def _frame(n=120, leak=False, with_mem=True):
    t = np.arange(n) * 2.0
    d = pd.DataFrame({"req_rate": 10.0, "err_rate": 0.1, "p95_s": 0.05, "cpu_cores": 0.1,
                      "up": 1.0, "mem_limit_bytes": 256e6}, index=t)
    if with_mem:
        d["mem_bytes"] = 100e6 + (np.arange(n) * 1.5e6 if leak else 0)
    return d


def test_isolated_p95_spike_does_not_look_like_a_latency_fault():
    """Regression: a window MAX of the p95 series made healthy traffic show lat_ratio 100+ (bucket-interpolation jumps)."""
    healthy = _frame()
    base = fit_baseline(healthy)
    spiky = healthy.copy()
    spiky.iloc[-3, spiky.columns.get_loc("p95_s")] = 0.9              # one bucket jump inside the last 10 s
    assert window_features(spiky, base, 10.0)["lat_ratio"] < 1.5
    slow = healthy.copy()
    slow.loc[slow.index > slow.index.max() - 10, "p95_s"] = 0.9      # the whole window is slow: a real fault
    assert window_features(slow, base, 10.0)["lat_ratio"] > 10


def test_old_restore_step_does_not_create_a_slope():
    """Regression: a 120 s slope lookback reached into the previous run's restore (a recreated container makes memory and
    disk jump), and that produced most of the detector's false alarms on healthy windows."""
    n = 120
    t = np.arange(n) * 2.0
    d = pd.DataFrame({"req_rate": 10.0, "err_rate": 0.0, "p95_s": 0.05, "cpu_cores": 0.1, "up": 1.0,
                      "mem_limit_bytes": 256e6, "mem_bytes": 100e6, "scratch_bytes": 0.0}, index=t)
    d.loc[d.index < 100, "mem_bytes"] = 240e6        # old container, near its limit ...
    d.loc[d.index < 100, "scratch_bytes"] = 700e6    # ... with a full scratch disk, then recreated: both drop to normal
    f = window_features(d, fit_baseline(d[d.index >= 100]), 10.0)
    assert abs(f["mem_slope_share_per_min"]) < 1e-6 and abs(f["scratch_slope_mb_per_min"]) < 1e-6


def test_disk_fill_is_visible_in_features():
    """Regression: no feature saw the scratch disk, so a filling disk looked like a generic error spike."""
    d = _frame()
    d["scratch_bytes"] = 0.0
    base = fit_baseline(d)
    filling = d.copy()
    filling["scratch_bytes"] = np.arange(len(d)) * 12e6
    f = window_features(filling, base, 10.0)
    assert f["scratch_mb"] > 1000 and f["scratch_slope_mb_per_min"] > 100
    quiet = window_features(d, base, 10.0)
    assert quiet["scratch_mb"] == 0 and quiet["scratch_slope_mb_per_min"] == 0


def test_healthy_window_is_near_baseline():
    d = _frame()
    f = window_features(d, fit_baseline(d))
    assert abs(f["rps_ratio"] - 1) < 1e-6 and abs(f["lat_ratio"] - 1) < 1e-6
    assert f["mem_slope_share_per_min"] < 1e-6


def test_leak_has_positive_slope_share():
    healthy = _frame()
    f = window_features(_frame(leak=True), fit_baseline(healthy))
    assert f["mem_slope_share_per_min"] > 0.1  # ~35% of limit per minute at this synthetic rate


def test_missing_signal_stays_nan_with_mask():
    healthy = _frame(with_mem=False)
    f = window_features(healthy, fit_baseline(healthy))
    assert np.isnan(f["mem_ratio"]) and f["mem_ratio_obs"] == 0.0
    assert np.isnan(f["deploys_3m"])  # never reported, never zero-filled


def test_feature_names_are_stable():
    f = window_features(_frame(), fit_baseline(_frame()))
    assert sorted(f) == FEATURE_NAMES
