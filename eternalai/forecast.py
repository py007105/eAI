"""Exhaustion forecast for gradual degradation (memory growth, scratch-disk growth).

Robust Theil-Sen trend with a confidence interval on the slope, turned into an exhaustion
window [earliest, latest]. It speaks only when growth is steady and the interval excludes zero;
it says nothing about sudden crashes and never claims to predict them.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import theilslopes


def forecast_exhaustion(series: pd.Series, limit: float, lookback_s: float = 120.0,
                        min_span_s: float = 30.0, confidence: float = 0.90) -> dict | None:
    s = series.dropna()
    if len(s) < 10 or not np.isfinite(limit) or limit <= 0:
        return None
    s = s[s.index > s.index[-1] - lookback_s]
    if len(s) < 10 or s.index[-1] - s.index[0] < min_span_s:
        return None
    x, y = s.index.values.astype(float), s.values.astype(float)
    slope, _, lo, hi = theilslopes(y, x, confidence)
    steady = float(np.mean(np.diff(y) >= 0))  # share of non-decreasing steps
    if lo <= 0 or steady < 0.8:
        return None  # flat, noisy, or not steadily rising: no forecast
    remaining = max(limit - y[-1], 0.0)
    return {"slope_per_min": float(slope * 60), "share_of_limit_now": float(y[-1] / limit),
            "eta_s": remaining / slope, "eta_earliest_s": remaining / hi, "eta_latest_s": remaining / lo,
            "confidence": confidence, "points": int(len(s)), "steady_fraction": round(steady, 2)}
