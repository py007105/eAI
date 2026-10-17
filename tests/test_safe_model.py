import numpy as np
import pytest
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import HistGradientBoostingClassifier

from eternalai.safe_model import SafeHGB


def data(n=120, seed=0):
    rng = np.random.default_rng(seed)
    y = rng.integers(0, 2, n)
    informative = y + rng.normal(0, 0.3, n)
    constant = np.full(n, 3.0)
    empty = np.full(n, np.nan)
    return np.column_stack([informative, constant, empty]), y


def test_plain_hgb_fails_on_constant_columns_but_safe_hgb_does_not():
    """Regression for the crash that killed the transfer experiment."""
    X, y = data()
    with pytest.raises(ValueError):
        HistGradientBoostingClassifier().fit(X, y)
    m = SafeHGB().fit(X, y)
    assert (m.predict(X) == y).mean() > 0.8 and m.keep_ == [0]


def test_columns_dropped_at_fit_are_ignored_at_predict_and_nan_is_kept():
    X, y = data()
    m = SafeHGB().fit(X, y)
    X2 = X.copy()
    X2[:, 1], X2[:, 2] = 99.0, 7.0                # changes in dropped columns must not matter
    assert np.array_equal(m.predict_proba(X), m.predict_proba(X2))
    X3 = X.copy()
    X3[0, 0] = np.nan                              # a missing value in a used column is handled natively
    assert np.isfinite(m.predict_proba(X3)).all()


def test_all_columns_uninformative_falls_back_to_prior():
    X, y = np.full((50, 2), np.nan), np.array([0] * 40 + [1] * 10)
    p = SafeHGB().fit(X, y).predict_proba(X)[0]
    assert abs(p[0] - 0.8) < 1e-9


def test_works_inside_calibration_multiclass():
    """The live classifier is multiclass and calibrated; constant columns must not break either step."""
    rng = np.random.default_rng(3)
    y = rng.integers(0, 3, 240)
    X = np.column_stack([y + rng.normal(0, 0.4, 240), np.full(240, 1.0), np.full(240, np.nan)])
    cal = CalibratedClassifierCV(SafeHGB(), method="sigmoid", cv=3).fit(X, y)
    p = cal.predict_proba(X)
    assert p.shape == (240, 3) and np.allclose(p.sum(1), 1.0) and (p.argmax(1) == y).mean() > 0.7
