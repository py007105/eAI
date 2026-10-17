import numpy as np
from sklearn.model_selection import KFold

from eternalai.novelty import NOVELTY_FEATURES, NoveltyGate


def windows(n, rng, kind):
    """Two known regimes (healthy; error-like) and one never-seen regime (cpu-like)."""
    X = np.full((n, len(NOVELTY_FEATURES)), np.nan)
    col = {f: i for i, f in enumerate(NOVELTY_FEATURES)}
    X[:, col["lat_ratio"]] = rng.normal(1, 0.05, n)
    X[:, col["cpu_per_req_ratio"]] = rng.normal(1, 0.1, n)
    X[:, col["error_ratio"]] = np.abs(rng.normal(0, 0.002, n))
    X[:, col["up_frac"]] = 1.0
    if kind == "errors":
        X[:, col["error_ratio"]] = rng.normal(0.7, 0.05, n)
    if kind == "cpu":
        X[:, col["cpu_per_req_ratio"]] = rng.normal(30, 3, n)
    return X


def gate(seed=0):
    rng = np.random.default_rng(seed)
    X = np.vstack([windows(600, rng, "healthy"), windows(150, rng, "errors")])
    folds = list(KFold(5, shuffle=True, random_state=0).split(X))
    return NoveltyGate().fit(X, folds), rng


def test_known_regimes_pass_and_unseen_regime_is_novel():
    g, rng = gate()
    known = np.vstack([windows(200, rng, "healthy"), windows(100, rng, "errors")])
    novel = windows(100, rng, "cpu")
    assert (g.distance(known) > g.threshold_).mean() < 0.05          # few false abstentions on known regimes
    assert (g.distance(novel) > g.threshold_).mean() > 0.95          # the never-seen regime is caught


def test_threshold_is_taken_from_out_of_fold_distances():
    g, _ = gate(1)
    assert np.isfinite(g.oof_).all() and g.threshold_ == np.nanquantile(g.oof_, 0.99)


def test_missing_values_stay_distinguishable_from_values():
    """A service that is not scraped (all NaN except up_frac) must not look identical to a healthy window."""
    g, rng = gate(2)
    healthy = windows(1, rng, "healthy")
    gone = np.full_like(healthy, np.nan)
    gone[0, NOVELTY_FEATURES.index("up_frac")] = 0.0
    assert g.distance(gone)[0] > g.distance(healthy)[0]


def test_dict_interface_matches_array_interface():
    g, rng = gate(3)
    x = windows(1, rng, "cpu")
    feats = dict(zip(NOVELTY_FEATURES, x[0]))
    assert abs(g.distance_of(feats) - g.distance(x)[0]) < 1e-12 and g.is_novel(feats)
