"""Root-cause ranking over the service graph.

Evidence per service (all observable): how anomalous it is, how early it became anomalous,
how many of its callers blame it through failed calls, how many of its callees are themselves
anomalous (a symptom may only be propagating up), and any recent release change. A shallow
gradient-boosted ranker (NaN-aware) fitted on training incidents turns the evidence into a
score; there are no hand-set weights. Baselines for comparison: `deepest_anomalous` (the old prototype's rule) and
`baro_rank` (robust z-score ranking, after RCAEval's BARO).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config

EVIDENCE = ["anomaly_score", "anomalous", "earliness", "caller_blame", "n_anomalous_callees",
            "n_anomalous_callers", "unavailable", "recent_deploy", "err_ratio", "lat_ratio"]


def evidence_table(scores: dict, anomalous: dict, onset: dict, depfail: dict, feats: dict,
                   topology=config.TOPOLOGY) -> pd.DataFrame:
    """One row per service. `onset[s]` = first anomalous time (or None); `depfail[(caller, callee)]` = failed
    call rate; `feats[s]` = latest window features."""
    callers = {s: [c for c, cs in topology.items() if s in cs] for s in topology}
    times = [t for t in onset.values() if t is not None]
    t_min, t_max = (min(times), max(times)) if times else (0, 0)
    rows = {}
    for s in topology:
        f = feats.get(s, {})
        blame = sum(depfail.get((c, s), 0.0) or 0.0 for c in callers[s])
        total = sum(depfail.get((c, k), 0.0) or 0.0 for c in callers[s] for k in topology[c]) or 1e-9
        e = (1.0 if t_max == t_min else 1 - (onset[s] - t_min) / (t_max - t_min)) if onset.get(s) is not None else 0.0
        rows[s] = {"anomaly_score": scores.get(s, np.nan), "anomalous": float(bool(anomalous.get(s))),
                   "earliness": e, "caller_blame": blame / total if blame else 0.0,
                   "n_anomalous_callees": sum(bool(anomalous.get(k)) for k in topology[s]),
                   "n_anomalous_callers": sum(bool(anomalous.get(c)) for c in callers[s]),
                   "unavailable": float(f.get("up_frac", 1.0) == 0),
                   "recent_deploy": float((f.get("deploys_3m") or 0) > 0),
                   "err_ratio": f.get("error_ratio", np.nan), "lat_ratio": f.get("lat_ratio", np.nan)}
    return pd.DataFrame.from_dict(rows, orient="index")[EVIDENCE]


class Ranker:
    def __init__(self, model, features=EVIDENCE):
        self.model, self.features = model, features

    def rank(self, table: pd.DataFrame) -> list[dict]:
        X = table[self.features].astype(float).values  # NaN stays NaN; the model is NaN-aware
        p = self.model.predict_proba(X)[:, 1]
        p = p / p.sum() if p.sum() > 0 else np.full(len(p), 1 / len(p))  # relative support across services
        order = np.argsort(-p)
        return [{"service": table.index[i], "score": float(p[i])} for i in order]


def deepest_anomalous(anomalous: dict, topology=config.TOPOLOGY) -> list[str]:
    """Old prototype rule: among anomalous services prefer the one whose callees are all healthy."""
    an = [s for s, a in anomalous.items() if a]
    deepest = [s for s in an if not any(anomalous.get(k) for k in topology[s])]
    return deepest + [s for s in an if s not in deepest]


def baro_rank(frame: dict, baseline: dict) -> list[str]:
    """BARO-style: rank services by the largest robust z-score of any signal against its healthy baseline."""
    best = {}
    for s, f in frame.items():
        zs = [abs(f[k]) for k in ("lat_z", "cpu_per_req_z", "mem_z", "error_ratio_z") if np.isfinite(f.get(k, np.nan))]
        best[s] = max(zs) if zs else 0.0
    return sorted(best, key=best.get, reverse=True)
