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
