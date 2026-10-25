"""Shared rolling-window features for ONE service.

The same function is used to build training rows from recorded evaluator runs and to
score live traffic, so train and serve cannot drift apart. Input is a DataFrame
indexed by time (seconds) with raw signals (any may be missing or NaN):

    req_rate, err_rate (errors per second), p95_s, mem_bytes, mem_limit_bytes,
    cpu_cores, up (1/0), dep_fail_rate, error_log_rate, deploys_3m (release changes in
    the last 3 min), restarts_3m (process restarts in the last 3 min)

`baseline` is a dict of healthy-period medians fitted on TRAINING data only
(see `fit_baseline`). Missing signals stay NaN: they are never zero-filled. Features
that cannot be computed come back NaN, plus an explicit `<name>_obs` mask column.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import theilslopes

SIGNALS = ["req_rate", "err_rate", "p95_s", "mem_bytes", "mem_limit_bytes", "cpu_cores", "up",
           "dep_fail_rate", "error_log_rate", "deploys_3m", "restarts_3m", "scratch_bytes"]
BASE_KEYS = ["req_rate", "p95_s", "cpu_cores", "mem_bytes", "error_ratio", "cpu_per_req"]
EPS = 1e-9


def _ratio(num, den):
    return num / den if den and np.isfinite(den) and den > EPS else np.nan


def _slope_per_min(s: pd.Series) -> float:
    s = s.dropna()
    if len(s) < 5 or s.index[-1] - s.index[0] < 10:
        return np.nan
    return float(theilslopes(s.values, s.index.values.astype(float))[0] * 60.0)


def fit_baseline(healthy: pd.DataFrame) -> dict:
    """Median and MAD of each base signal over healthy rows (fit on training folds only)."""
    d = healthy.copy()
    d["error_ratio"] = d["err_rate"] / d["req_rate"].where(d["req_rate"] > EPS)
    d["cpu_per_req"] = d["cpu_cores"] / d["req_rate"].where(d["req_rate"] > 0.5)  # traffic-normalised CPU
    out = {}
    for k in BASE_KEYS:
        v = d[k].dropna() if k in d else pd.Series(dtype=float)
        if len(v):
            med = float(v.median())
            mad = float((v - med).abs().median()) * 1.4826
            out[k] = (med, max(mad, 1e-6))
    return out


def window_features(df: pd.DataFrame, baseline: dict, window_s: float = 30.0) -> dict:
    """Features for the last `window_s` seconds of `df`. Returns a flat dict of floats."""
    w = df[df.index > df.index.max() - window_s]
    f: dict[str, float] = {}

    def mean(c):
        return float(w[c].mean()) if c in w and w[c].notna().any() else np.nan

    rps, err = mean("req_rate"), mean("err_rate")
    # Median, not max: p95 interpolated from coarse histogram buckets at a few requests per second jumps between
    # buckets, so a window MAX looked like a 100x latency spike in healthy traffic (99th percentile of the ratio was
    # 535 in attempt 2). A real latency fault moves the whole series, which the median still sees.
    p95 = float(w["p95_s"].median()) if "p95_s" in w and w["p95_s"].notna().any() else np.nan
    cpu, mem = mean("cpu_cores"), mean("mem_bytes")
    err_ratio = _ratio(err, rps) if np.isfinite(err) else np.nan

    def rel(key, value):
        b = baseline.get(key)
        if b is None or not np.isfinite(value):
            return np.nan, np.nan
        med, mad = b
        return _ratio(value, med), (value - med) / mad

    f["rps_ratio"], f["rps_z"] = rel("req_rate", rps)
    f["lat_ratio"], f["lat_z"] = rel("p95_s", p95)
    f["cpu_ratio"], f["cpu_z"] = rel("cpu_cores", cpu)
    f["mem_ratio"], f["mem_z"] = rel("mem_bytes", mem)
    cpr = cpu / rps if np.isfinite(cpu) and np.isfinite(rps) and rps > 0.5 else np.nan
    f["cpu_per_req_ratio"], f["cpu_per_req_z"] = rel("cpu_per_req", cpr)
    f["error_ratio"] = err_ratio
    f["error_ratio_z"] = rel("error_ratio", err_ratio)[1]
    f["error_ratio_delta"] = (err_ratio - baseline["error_ratio"][0]) if "error_ratio" in baseline and np.isfinite(err_ratio) else np.nan

    limit = mean("mem_limit_bytes")
    f["mem_share"] = _ratio(mem, limit) if np.isfinite(limit) and limit > 0 else np.nan
    # Slope lookback is short (>= 20 s, 2 windows). A 120 s lookback reached into the previous run's restore, where a
    # recreated container makes memory/disk jump, and produced most of the detector's false alarms. Slow, gradual growth is
    # the forecaster's job (engine/forecast.py), which keeps its own longer lookback.
    slope_n = int(max(2 * window_s, 20.0) / 2) + 1
    mem_s = df["mem_bytes"].tail(slope_n) if "mem_bytes" in df else pd.Series(dtype=float)
    slope = _slope_per_min(mem_s)
    f["mem_slope_share_per_min"] = _ratio(slope, limit) if np.isfinite(slope) and np.isfinite(limit) and limit > 0 else np.nan
    # v2 (Amendment 4, E2): memory growth relative to the service's OWN recent past, in share of its limit. The absolute level (mem_ratio, mem_z,
    # mem_share) depends on how long the container has lived and on what load it has seen (v1: a few MB of drift put healthy services outside tight
    # learned limits); growth against the same container's earlier history does not. Baseline = median memory 150 s to 60 s ago.
    mem_hist = df["mem_bytes"] if "mem_bytes" in df else pd.Series(dtype=float)
    past = mem_hist[(mem_hist.index > df.index.max() - 150.0) & (mem_hist.index <= df.index.max() - 60.0)].dropna()
    f["mem_rel_growth"] = ((mem - float(past.median())) / limit) if len(past) >= 10 and np.isfinite(mem) and np.isfinite(limit) and limit > 0 else np.nan
    # scratch-disk usage (MB) and its growth: the signature of a filling disk (absent from attempt 1-2 features)
    f["scratch_mb"] = mean("scratch_bytes") / 1e6 if np.isfinite(mean("scratch_bytes")) else np.nan
    sc_s = df["scratch_bytes"].tail(slope_n) if "scratch_bytes" in df else pd.Series(dtype=float)
    sc_slope = _slope_per_min(sc_s)
    f["scratch_slope_mb_per_min"] = sc_slope / 1e6 if np.isfinite(sc_slope) else np.nan
    f["up_frac"] = mean("up")
    f["dep_fail_rate"] = mean("dep_fail_rate")
    f["error_log_rate"] = mean("error_log_rate")
    f["deploys_3m"] = float(w["deploys_3m"].dropna().iloc[-1]) if "deploys_3m" in w and w["deploys_3m"].notna().any() else np.nan
    r = w["restarts_3m"].dropna() if "restarts_3m" in w else pd.Series(dtype=float)
    f["restarts_in_window"] = float(max(r.iloc[-1] - r.iloc[0], 0)) if len(r) else np.nan  # restarts seen inside the window
    for k in list(f):
        f[f"{k}_obs"] = float(np.isfinite(f[k]))
    return f


FEATURE_NAMES = sorted(window_features(
    pd.DataFrame({c: [np.nan] * 6 for c in SIGNALS}, index=np.arange(6) * 2.0), {}).keys())
