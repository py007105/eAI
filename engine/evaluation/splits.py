"""Leakage-safe splits and diagnostics shared by every model evaluation.

* grouped_folds: whole incidents never straddle train/test.
* loso_folds: leave one SYSTEM out (the honest cross-system test).
All preprocessing must be fitted inside each fold on the training part only.
"""
from __future__ import annotations

import numpy as np
from sklearn.model_selection import GroupKFold, StratifiedGroupKFold


def grouped_folds(y, groups, n_splits=5, seed=0):
    sgkf = StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=seed)
    yield from sgkf.split(np.zeros(len(y)), y, groups)


def loso_folds(systems):
    systems = np.asarray(systems)
    for s in np.unique(systems):
        yield s, np.where(systems != s)[0], np.where(systems == s)[0]


def assert_no_group_overlap(train_idx, test_idx, groups):
    g = np.asarray(groups)
    overlap = set(g[train_idx]) & set(g[test_idx])
    assert not overlap, f"{len(overlap)} incidents appear in both train and test"
