"""Novelty gate: is this window unlike anything the classifier was trained on?

A classifier's softmax confidence says nothing about novelty: a never-seen fault (cpu_burn) was labelled `latency_spike` or
`down` with high confidence, and abstention on held-out fault types was 0-7% for four of six types
(docs/results/models_cv.md, attempt 4). The gate measures the mean distance from a window to its k nearest KNOWN windows
(healthy and the known faults) in a robust-scaled feature space, and abstains when that distance exceeds a threshold taken
from OUT-OF-FOLD distances (how far windows of held-out runs are from the training runs), so it does not shrink to zero on
the training data itself.

NaN is imputed by the training median ONLY inside this distance computation, with an explicit observed-mask for each
feature so "missing" stays distinguishable; the classifier itself still sees NaN as NaN.
"""
from __future__ import annotations

import warnings

import numpy as np
from sklearn.neighbors import NearestNeighbors

# Signals that describe how a window looks; masks (_obs) are appended internally.
NOVELTY_FEATURES = ["lat_ratio", "cpu_per_req_ratio", "error_ratio", "dep_fail_rate", "error_log_rate", "mem_rel_growth",
                    "mem_slope_share_per_min", "scratch_mb", "scratch_slope_mb_per_min", "up_frac", "deploys_3m",
                    "restarts_in_window"]


class NoveltyGate:
    def __init__(self, features=None, k: int = 5, quantile: float = 0.99):
        self.features, self.k, self.quantile = list(features or NOVELTY_FEATURES), k, quantile

    # ---- representation
    def _fit_scaler(self, X):
        with warnings.catch_warnings():            # all-NaN columns are legitimate (a signal a system does not have)
            warnings.simplefilter("ignore", RuntimeWarning)
            self.med_ = np.nanmedian(X, axis=0)
            sd = np.nanstd(X, axis=0)
        self.med_ = np.where(np.isfinite(self.med_), self.med_, 0.0)
        self.sd_ = np.where(np.isfinite(sd) & (sd > 1e-9), sd, 1.0)

    def _z(self, X):
        X = np.asarray(X, dtype=float)
        mask = np.isfinite(X).astype(float)
        Z = np.arcsinh((np.where(np.isfinite(X), X, self.med_) - self.med_) / self.sd_)  # heavy tails -> log-like
        return np.hstack([Z, mask])

    def matrix(self, df):
        return df[self.features].to_numpy(dtype=float)

    # ---- fitting
    def fit(self, X_train, folds=None):
        """`X_train`: array of training windows. `folds`: list of (train_idx, test_idx) partitions grouped by run; they
        are used to take out-of-fold distances for the threshold."""
        X_train = np.asarray(X_train, dtype=float)
        self._fit_scaler(X_train)
        Z = self._z(X_train)
        self.nn_ = NearestNeighbors(n_neighbors=self.k).fit(Z)
        oof = np.full(len(Z), np.nan)
        for tr, te in (folds or []):
            nn = NearestNeighbors(n_neighbors=min(self.k, len(tr))).fit(Z[tr])
            oof[te] = nn.kneighbors(Z[te])[0].mean(axis=1)
        if np.isfinite(oof).any():
            self.threshold_ = float(np.nanquantile(oof, self.quantile))
        else:  # no folds given: fall back to leave-self-out distances (optimistic, flagged by oof_ being absent)
            self.threshold_ = float(np.quantile(self.nn_.kneighbors(Z, n_neighbors=self.k + 1)[0][:, 1:].mean(axis=1),
                                                self.quantile))
        self.oof_ = oof
        return self

    # ---- scoring
    def distance(self, X):
        return self.nn_.kneighbors(self._z(X))[0].mean(axis=1)

    def distance_of(self, feats: dict) -> float:
        x = np.array([[feats.get(f, np.nan) for f in self.features]], dtype=float)
        return float(self.distance(x)[0])

    def is_novel(self, feats: dict) -> bool:
        return self.distance_of(feats) > self.threshold_
