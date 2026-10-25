"""Gradient boosting that survives constant or empty feature columns in a training fold.

scikit-learn's HistGradientBoostingClassifier raises ("window shape cannot be larger than input array
shape") when a column has fewer than two distinct finite values in the data it is fitted on. That happens
legitimately when a fold trains on one system or one run family where a signal is absent or constant.
SafeHGB drops such columns at fit time (decided from the TRAINING data only, remembered, and applied
identically at predict time). NaN elsewhere stays NaN: nothing is imputed.
"""
from __future__ import annotations

import numpy as np
from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import HistGradientBoostingClassifier


class SafeHGB(BaseEstimator, ClassifierMixin):
    def __init__(self, max_depth=3, max_iter=100, learning_rate=0.05, min_samples_leaf=20,
                 l2_regularization=1.0, class_weight=None, random_state=0):
        self.max_depth, self.max_iter, self.learning_rate = max_depth, max_iter, learning_rate
        self.min_samples_leaf, self.l2_regularization = min_samples_leaf, l2_regularization
        self.class_weight, self.random_state = class_weight, random_state

    def fit(self, X, y):
        X = np.asarray(X, dtype=float)
        self.keep_ = [j for j in range(X.shape[1]) if len(np.unique(X[:, j][np.isfinite(X[:, j])])) >= 2]
        if self.keep_:
            self.model_ = HistGradientBoostingClassifier(
                max_depth=self.max_depth, max_iter=self.max_iter, learning_rate=self.learning_rate,
                min_samples_leaf=self.min_samples_leaf, l2_regularization=self.l2_regularization,
                class_weight=self.class_weight, random_state=self.random_state).fit(X[:, self.keep_], y)
        else:  # nothing informative to learn from: fall back to the class prior
            self.model_ = DummyClassifier(strategy="prior").fit(X, y)
        self.classes_ = self.model_.classes_
        return self

    def _x(self, X):
        X = np.asarray(X, dtype=float)
        return X[:, self.keep_] if self.keep_ else X

    def predict_proba(self, X):
        return self.model_.predict_proba(self._x(X))

    def predict(self, X):
        return self.model_.predict(self._x(X))
