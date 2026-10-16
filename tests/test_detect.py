import numpy as np

from eternalai.detect import FEATURES, Persistence, fit_service


def healthy(n, rng):
    X = np.column_stack([rng.normal(1, 0.05, n), rng.normal(1, 0.1, n), np.abs(rng.normal(0, 0.002, n)),
                         np.abs(rng.normal(0, 0.01, n)), np.abs(rng.normal(0, 0.01, n)),
                         rng.normal(0.25, 0.01, n), rng.normal(0, 0.001, n), np.ones(n)])
    assert X.shape[1] == len(FEATURES)
    return X


def test_detector_flags_fault_not_healthy():
    rng = np.random.default_rng(0)
    d = fit_service(healthy(600, rng), healthy(600, rng))
    ok = healthy(300, rng)
    fp = np.mean([-d.model.score_samples(r[None])[0] > d.threshold for r in ok])
    bad = dict(zip(FEATURES, [4.0, 1.0, 0.6, 1.0, 3.0, 0.25, 0.0, 1.0]))  # latency + errors
    assert fp < 0.05 and d.anomalous(bad)


def test_nan_features_are_accepted():
    rng = np.random.default_rng(1)
    d = fit_service(healthy(300, rng), healthy(300, rng))
    assert np.isfinite(d.score({"lat_ratio": np.nan, "up_frac": 1.0}))


def test_persistence_needs_consecutive_ticks():
    p = Persistence(3)
    assert [p.update("web", a) for a in (True, True, False, True, True, True)] == [False, False, False, False, False, True]
