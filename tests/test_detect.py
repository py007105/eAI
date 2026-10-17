import numpy as np

from eternalai.detect import FEATURES, Persistence, fit_service


def healthy(n, rng):
    cols = {"lat_ratio": rng.normal(1, 0.05, n), "cpu_per_req_ratio": rng.normal(1, 0.1, n),
            "error_ratio": np.abs(rng.normal(0, 0.002, n)), "dep_fail_rate": np.abs(rng.normal(0, 0.01, n)),
            "error_log_rate": np.abs(rng.normal(0, 0.01, n)), "mem_share": rng.normal(0.25, 0.01, n),
            "mem_slope_share_per_min": rng.normal(0, 0.001, n), "scratch_mb": np.zeros(n),
            "scratch_slope_mb_per_min": np.zeros(n), "up_frac": np.ones(n)}
    return np.column_stack([cols[f] for f in FEATURES])


def row(**over):
    base = dict(zip(FEATURES, healthy(1, np.random.default_rng(0))[0]))
    base.update(over)
    return base


def test_detector_flags_fault_not_healthy():
    rng = np.random.default_rng(0)
    d = fit_service(healthy(600, rng), healthy(600, rng))
    fp = np.mean([d.anomalous(dict(zip(FEATURES, r))) for r in healthy(400, rng)])
    assert fp < 0.05 and d.anomalous(row(lat_ratio=4.0, error_ratio=0.6, error_log_rate=3.0))


def test_single_feature_excursions_are_caught():
    """Regression: IsolationForest alone scored a 78% error ratio below the healthy 99th percentile, because that
    feature is almost constant in healthy data. Learned healthy-range limits catch it."""
    rng = np.random.default_rng(1)
    d = fit_service(healthy(800, rng), healthy(800, rng))
    for over in ({"error_ratio": 0.78}, {"scratch_mb": 120.0}, {"lat_ratio": 20.0}, {"mem_slope_share_per_min": 0.05}):
        assert d.anomalous(row(**over)), over
    assert d.out_of_range(row(error_ratio=0.78)) == ["error_ratio"]


def test_live_decision_uses_limits_not_only_the_forest_score():
    """Regression (found by the live smoke test): the engine compared only the forest score with its threshold, so a
    1.4 s latency fault (lat_ratio ~28) was never flagged live although it is flagged 100% offline."""
    from eternalai.detect import service_anomalous
    rng = np.random.default_rng(5)
    d = fit_service(healthy(800, rng), healthy(800, rng))
    latency_fault = row(lat_ratio=28.0)
    assert d.score(latency_fault) <= d.threshold                 # the forest alone does NOT flag it
    assert service_anomalous(d, latency_fault, down=False)       # the live decision does
    assert service_anomalous(d, row(), down=True)                # not scraped => anomalous
    assert not service_anomalous(d, row(), down=False)


def test_limits_come_from_healthy_data_only_and_do_not_fire_on_healthy():
    rng = np.random.default_rng(2)
    tr, va = healthy(800, rng), healthy(800, rng)
    d = fit_service(tr, va)
    for f, (lo, hi) in d.limits.items():
        j = FEATURES.index(f)
        allv = np.concatenate([tr[:, j], va[:, j]])
        assert lo <= allv.min() and hi >= allv.max()        # the healthy range is inside the limits
    fresh = healthy(2000, rng)
    rate = np.mean([bool(d.out_of_range(dict(zip(FEATURES, r)))) for r in fresh])
    assert rate < 0.01                                      # a small false-alarm rate on unseen healthy windows


def test_nan_features_are_accepted_and_never_flag_by_themselves():
    rng = np.random.default_rng(3)
    d = fit_service(healthy(300, rng), healthy(300, rng))
    assert np.isfinite(d.score({"lat_ratio": np.nan, "up_frac": 1.0}))
    assert d.out_of_range({"lat_ratio": np.nan, "error_ratio": np.nan}) == []   # missing is not an excursion


def test_persistence_needs_consecutive_ticks():
    p = Persistence(3)
    assert [p.update("web", a) for a in (True, True, False, True, True, True)] == [False, False, False, False, False, True]
