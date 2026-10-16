"""Anomaly detector: one IsolationForest per service on traffic-normalised healthy windows.

The score is an anomaly ranking, NOT a probability. The decision threshold is set from held-out
healthy windows (a target false-alarm rate), and an incident needs several consecutive
anomalous ticks. A service that is not being scraped is handled by an explicit rule, because a
missing value is not a normal one.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from sklearn.ensemble import IsolationForest

# Traffic-normalised signals only: a healthy surge must not look anomalous.
FEATURES = ["lat_ratio", "cpu_per_req_ratio", "error_ratio", "dep_fail_rate", "error_log_rate",
            "mem_share", "mem_slope_share_per_min", "up_frac"]


@dataclass
class ServiceDetector:
    model: IsolationForest
    threshold: float
    features: list[str] = field(default_factory=lambda: list(FEATURES))

    def score(self, feats: dict) -> float:
        x = np.array([[feats.get(f, np.nan) for f in self.features]], dtype=float)
        return float(-self.model.score_samples(x)[0])  # higher = more anomalous

    def anomalous(self, feats: dict) -> bool:
        return self.score(feats) > self.threshold


def fit_service(train: np.ndarray, validation: np.ndarray, target_fpr: float = 0.002,
                seed: int = 0) -> ServiceDetector:
    """Fit on healthy training windows; set the threshold from healthy VALIDATION windows."""
    model = IsolationForest(n_estimators=200, max_samples=min(256, len(train)), contamination="auto",
                            random_state=seed).fit(train)
    val_scores = -model.score_samples(validation)
    thr = float(np.quantile(val_scores, 1 - target_fpr))
    return ServiceDetector(model, thr)


class Persistence:
    """Open an incident only after `k` consecutive anomalous ticks for the same service."""

    def __init__(self, k: int = 3):
        self.k, self.runs = k, {}

    def update(self, service: str, anomalous: bool) -> bool:
        self.runs[service] = self.runs.get(service, 0) + 1 if anomalous else 0
        return self.runs[service] >= self.k
