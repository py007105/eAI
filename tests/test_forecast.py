import numpy as np
import pandas as pd

from engine.forecast import forecast_exhaustion

LIMIT = 256e6


def series(values, step=2.0):
    return pd.Series(values, index=np.arange(len(values)) * step)


def test_steady_growth_gives_window_that_contains_truth():
    n = 25  # 48 s of data growing 3 MB/s from 60 MB, still below the limit
    y = 60e6 + np.arange(n) * 6e6 + np.random.default_rng(0).normal(0, 2e5, n)
    f = forecast_exhaustion(series(y), LIMIT)
    true_eta = (LIMIT - y[-1]) / 3e6
    assert f and f["eta_earliest_s"] <= true_eta <= f["eta_latest_s"]


def test_flat_series_has_no_forecast():
    assert forecast_exhaustion(series(np.full(40, 100e6) + np.random.default_rng(1).normal(0, 1e5, 40)), LIMIT) is None


def test_sudden_jump_is_not_forecast_as_gradual():
    y = np.concatenate([np.full(30, 80e6), np.full(10, 240e6)])
    assert forecast_exhaustion(series(y), LIMIT) is None


def test_missing_data_stays_missing():
    assert forecast_exhaustion(series(np.full(40, np.nan)), LIMIT) is None
