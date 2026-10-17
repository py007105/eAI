"""Anomaly detector: per service, trained on healthy, traffic-normalised windows only (no fault labels).

Two parts, both learned from healthy data:
  * an IsolationForest for JOINT, multivariate oddness;
  * learned healthy-range limits per feature, for single-feature excursions. The forest alone cannot flag these: with
    eight features, a feature that is almost constant in healthy data (error ratio 0, disk usage 0) gives it nothing to
    split on, so a 78% error ratio scored only 0.59 against a healthy 99th percentile of 0.70 (see
    docs/results/models_cv_attempt1.md and docs/DATA.md).

The anomaly score is a ranking, NOT a probability. A service that is not being scraped is handled by an explicit rule
in the caller, because a missing value is not a normal one. An incident needs several consecutive anomalous ticks.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from sklearn.ensemble import IsolationForest

# Traffic-normalised signals only: a healthy surge must not look anomalous.
FEATURES = ["lat_ratio", "cpu_per_req_ratio", "error_ratio", "dep_fail_rate", "error_log_rate",
            "mem_share", "mem_slope_share_per_min", "scratch_mb", "scratch_slope_mb_per_min", "up_frac"]
# Direction in which a feature indicates trouble. up_frac is handled by the caller's "not scraped" rule.
UPPER = {"lat_ratio", "error_ratio", "dep_fail_rate", "error_log_rate", "mem_share", "mem_slope_share_per_min",
         "scratch_mb", "scratch_slope_mb_per_min"}
TWO_SIDED = {"cpu_per_req_ratio"}   # busy loops and failing-fast services both move CPU per request
LIMIT_FEATURES = sorted(UPPER | TWO_SIDED)


@dataclass
class ServiceDetector:
    model: IsolationForest
    threshold: float
    limits: dict = field(default_factory=dict)     # feature -> (lo, hi) healthy limits
    features: list[str] = field(default_factory=lambda: list(FEATURES))

    def _x(self, feats: dict):
        return np.array([[feats.get(f, np.nan) for f in self.features]], dtype=float)

    def score(self, feats: dict) -> float:
        return float(-self.model.score_samples(self._x(feats))[0])  # higher = more anomalous

    def out_of_range(self, feats: dict) -> list[str]:
        out = []
        for f, (lo, hi) in self.limits.items():
            v = feats.get(f, np.nan)
            if np.isfinite(v) and (v > hi or (f in TWO_SIDED and v < lo)):
                out.append(f)
        return out

    def anomalous(self, feats: dict) -> bool:
        return self.score(feats) > self.threshold or bool(self.out_of_range(feats))


def learn_limits(healthy: np.ndarray, features, margin: float = 0.25) -> dict:
    """Healthy limits: the observed healthy range plus a margin of `margin` times the healthy spread
    (q99 - q50, floored at 2% of the largest observed magnitude so near-constant features still get a margin)."""
    lim = {}
    for f in LIMIT_FEATURES:
        j = list(features).index(f)
        v = healthy[:, j]
        v = v[np.isfinite(v)]
        if len(v) < 20:
            continue
        med, vmax, vmin = np.median(v), v.max(), v.min()
        spread = max(np.quantile(v, 0.99) - med, 0.02 * max(abs(vmax), abs(vmin), 1e-9))
        lim[f] = (float(vmin - margin * spread), float(vmax + margin * spread))
    return lim


def fit_service(train: np.ndarray, validation: np.ndarray, target_fpr: float = 0.002, seed: int = 0) -> ServiceDetector:
    """IsolationForest on healthy training windows; its threshold from healthy VALIDATION windows (held-out runs);
    limits from training plus validation healthy windows (still healthy-only)."""
    model = IsolationForest(n_estimators=200, max_samples=min(256, len(train)), contamination="auto",
                            random_state=seed).fit(train)
    thr = float(np.quantile(-model.score_samples(validation), 1 - target_fpr))
    return ServiceDetector(model, thr, learn_limits(np.vstack([train, validation]), list(FEATURES)))


class Persistence:
    """Open an incident only after `k` consecutive anomalous ticks for the same service."""

    def __init__(self, k: int = 3):
        self.k, self.runs = k, {}

    def update(self, service: str, anomalous: bool) -> bool:
        self.runs[service] = self.runs.get(service, 0) + 1 if anomalous else 0
        return self.runs[service] >= self.k
