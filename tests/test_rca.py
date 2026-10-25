"""rca.py: the evidence table on the shop topology, the ranker's normalisation, and the two baseline rankings."""
import numpy as np

from engine import config
from engine.rca import EVIDENCE, Ranker, baro_rank, deepest_anomalous, evidence_table

S = list(config.SERVICES)


def payments_down_case():
    """payments is down; orders' calls to payments fail; web and orders are anomalous as victims."""
    anomalous = {"web": True, "orders": True, "payments": True, "inventory": False}
    onset = {"payments": 100.0, "orders": 104.0, "web": 106.0, "inventory": None}
    depfail = {("orders", "payments"): 3.0, ("web", "orders"): 1.0}
    feats = {"payments": {"up_frac": 0.0, "error_ratio": np.nan},
             "orders": {"up_frac": 1.0, "error_ratio": 0.4, "lat_ratio": 2.0, "deploys_3m": 0},
             "web": {"up_frac": 1.0, "error_ratio": 0.3, "lat_ratio": 1.5},
             "inventory": {"up_frac": 1.0, "error_ratio": 0.0, "lat_ratio": 1.0, "deploys_3m": 1}}
    scores = {"web": 0.9, "orders": 0.95, "payments": 1.2, "inventory": 0.1}
    return scores, anomalous, onset, depfail, feats


def test_evidence_table_points_at_the_root():
    t = evidence_table(*payments_down_case())
    assert list(t.columns) == EVIDENCE and set(t.index) == set(S)
    p, o, w, i = (t.loc[s] for s in ("payments", "orders", "web", "inventory"))
    assert p.earliness == 1.0 and w.earliness == 0.0 and i.earliness == 0.0          # first anomalous = earliest
    assert p.unavailable == 1.0 and o.unavailable == 0.0
    assert p.caller_blame > 0 and p.n_anomalous_callees == 0                         # blamed, and nothing below it
    assert o.n_anomalous_callees == 1 and o.n_anomalous_callers == 1                 # orders calls a sick service
    assert i.recent_deploy == 1.0 and o.recent_deploy == 0.0
    assert np.isnan(p.err_ratio)                                                     # missing stays missing


def test_deepest_anomalous_rule():
    _, anomalous, *_ = payments_down_case()
    order = deepest_anomalous(anomalous)
    assert order[0] == "payments" and set(order) == {"payments", "orders", "web"}


class ConstModel:
    def __init__(self, p):
        self.p = np.asarray(p, dtype=float)

    def predict_proba(self, X):
        assert X.shape == (len(self.p), len(EVIDENCE))
        return np.c_[1 - self.p, self.p]


def test_ranker_normalises_and_orders():
    t = evidence_table(*payments_down_case())
    out = Ranker(ConstModel([0.1, 0.2, 0.6, 0.1])).rank(t)
    assert out[0]["service"] == t.index[2] and abs(sum(r["score"] for r in out) - 1) < 1e-9
    flat = Ranker(ConstModel([0, 0, 0, 0])).rank(t)
    assert all(abs(r["score"] - 0.25) < 1e-9 for r in flat)          # no support anywhere: uniform, not a division by zero


def test_baro_rank_uses_the_largest_finite_z():
    frame = {"web": {"lat_z": 1.0}, "orders": {"lat_z": np.nan, "mem_z": -7.0}, "payments": {"error_ratio_z": 3.0},
             "inventory": {}}
    assert baro_rank(frame, {}) == ["orders", "payments", "web", "inventory"]
