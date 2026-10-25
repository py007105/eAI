"""Temperature-scaling calibration that cannot change which class wins.

Per-class (one-vs-rest) sigmoid calibration, fitted on the few runs available per rare fault class, flattened every
fault probability towards its base rate and made the big "healthy" class win (attempt 1-2: calibrated recall 0 for four
fault classes where the uncalibrated model had 0.87-1.0). Temperature scaling has ONE parameter, so the arg-max (the
predicted class) is unchanged and only the confidence is adjusted. T is fitted on out-of-fold predictions from a grouped
inner cross-validation, i.e. on data the base model did not train on.
"""
from __future__ import annotations

import numpy as np
from scipy.optimize import minimize_scalar
from sklearn.base import BaseEstimator, ClassifierMixin, clone


def _scale(P, T):
    L = np.log(np.clip(P, 1e-6, 1.0)) / T
    L -= L.max(axis=1, keepdims=True)
    E = np.exp(L)
    return E / E.sum(axis=1, keepdims=True)


class TemperatureCalibrated(BaseEstimator, ClassifierMixin):
    def __init__(self, base, cv=None):
        self.base, self.cv = base, cv   # cv: list of (train_idx, test_idx) partitions of the training rows

    def fit(self, X, y):
        X, y = np.asarray(X, dtype=float), np.asarray(y)
        classes = np.unique(y)
        oof = np.full((len(y), len(classes)), 1e-6)
        for tr, te in self.cv:
            m = clone(self.base).fit(X[tr], y[tr])
            full = np.full((len(te), len(classes)), 1e-6)
            full[:, np.searchsorted(classes, m.classes_)] = m.predict_proba(X[te])
            oof[te] = full
        idx = np.searchsorted(classes, y)

        def nll(logT):
            return -np.mean(np.log(np.clip(_scale(oof, np.exp(logT))[np.arange(len(y)), idx], 1e-9, 1)))
        self.T_ = float(np.exp(minimize_scalar(nll, bounds=(-2.0, 3.0), method="bounded").x))
        self.model_ = clone(self.base).fit(X, y)
        self.classes_ = self.model_.classes_
        return self

    def predict_proba(self, X):
        return _scale(self.model_.predict_proba(np.asarray(X, dtype=float)), self.T_)

    def predict(self, X):
        return self.classes_[self.predict_proba(X).argmax(1)]
