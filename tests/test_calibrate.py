import numpy as np
from sklearn.calibration import CalibratedClassifierCV
from sklearn.model_selection import KFold

from engine.calibrate import TemperatureCalibrated
from engine.safe_model import SafeHGB


def rare_class_data(seed=0):
    """Healthy is 95% of rows; two rare fault classes are cleanly separable but have few rows (few runs in practice)."""
    rng = np.random.default_rng(seed)
    n = 1200
    y = rng.choice([0, 1, 2], size=n, p=[0.95, 0.025, 0.025])
    X = np.column_stack([y + rng.normal(0, 0.15, n), rng.normal(0, 1, n)])
    return X, y


def splits(n, k=3):
    return list(KFold(k, shuffle=True, random_state=0).split(np.arange(n)))


def test_prediction_is_unchanged_by_calibration():
    """Regression: sigmoid calibration turned a model with recall ~1 on rare classes into one with recall 0."""
    X, y = rare_class_data()
    base = SafeHGB(max_depth=3, max_iter=60, class_weight="balanced")
    cal = TemperatureCalibrated(base, splits(len(y))).fit(X, y)
    assert np.array_equal(cal.predict(X), cal.model_.predict(X))           # arg-max cannot move
    rec = [(cal.predict(X)[y == c] == c).mean() for c in (1, 2)]
    assert min(rec) > 0.8


def test_probabilities_are_valid_and_temperature_is_positive():
    X, y = rare_class_data(1)
    cal = TemperatureCalibrated(SafeHGB(max_iter=40), splits(len(y))).fit(X, y)
    P = cal.predict_proba(X)
    assert np.allclose(P.sum(1), 1) and (P >= 0).all() and cal.T_ > 0


def test_temperature_reduces_overconfidence_on_noisy_labels():
    rng = np.random.default_rng(2)
    n = 1500
    X = rng.normal(size=(n, 3))
    y = (X[:, 0] + rng.normal(0, 1.2, n) > 0).astype(int)                  # noisy: a boosted model will be overconfident
    base = SafeHGB(max_depth=6, max_iter=200, learning_rate=0.2, min_samples_leaf=3)
    tr, te = np.arange(0, 1000), np.arange(1000, n)
    cal = TemperatureCalibrated(base, splits(len(tr))).fit(X[tr], y[tr])
    raw_conf = cal.model_.predict_proba(X[te]).max(1)
    cal_conf = cal.predict_proba(X[te]).max(1)
    acc = (cal.predict(X[te]) == y[te]).mean()
    assert abs(cal_conf.mean() - acc) < abs(raw_conf.mean() - acc)         # closer to the true accuracy
    assert cal.T_ > 1.0                                                    # it learned to soften


def test_sigmoid_calibration_really_was_the_problem():
    """Documents the failure this module replaces: on rare classes the one-vs-rest sigmoid loses recall."""
    X, y = rare_class_data(3)
    base = SafeHGB(max_depth=3, max_iter=60, class_weight="balanced")
    sig = CalibratedClassifierCV(base, method="sigmoid", cv=splits(len(y))).fit(X, y)
    ours = TemperatureCalibrated(base, splits(len(y))).fit(X, y)
    rec = lambda m: np.mean([(m.predict(X)[y == c] == c).mean() for c in (1, 2)])
    assert rec(ours) >= rec(sig)
