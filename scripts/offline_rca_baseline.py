"""OFFLINE root-cause baselines on the training runs (not part of any live arm, not a benchmark result).

    python scripts/offline_rca_baseline.py [--runs data/runs] [--out docs/results/offline_rca_baseline.md]

Compares RCAEval/PyRCA-style rankers on the same incident definition that models/train_models.py uses for its ranker table (fault runs, service windows
at 10, 14, 20, 30 and 40 s after injection, all four services present):
  - baro:   BARO-style, rank services by the largest robust z-score of any signal against the healthy baseline (re-implementation, not RCAEval's package)
  - walk:   PyRCA/RCD-style random walk with restart over the service call graph, transition weights from anomaly scores (simplified re-implementation)
  - errors: rank by the error-ratio z-score alone (naive)
  - random: seeded random order
None of these is trained, so nothing leaks between runs; results are still pooled by RUN (bootstrap resamples whole runs). The learned ranker's out-of-fold
number comes from `models/train_models.py` (docs/results/models_cv.md, same incident definition) and is NOT recomputed here.
RE2/RE3 are not downloaded; nothing here says anything about them. Run only after the benchmark has finished.
"""
import argparse
import sys
import zlib
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "models"))

SERVICES = ["web", "orders", "inventory", "payments"]
TOPOLOGY = {"web": ["orders", "inventory"], "orders": ["inventory", "payments"], "inventory": [], "payments": []}
Z_COLS = ("lat_z", "cpu_per_req_z", "mem_z", "error_ratio_z")
HEALTHY_SCEN = {"traffic_surge", "good_deploy"}
DELAYS = (10, 14, 20, 30, 40)
METHODS = {"baro": "BARO-style robust z (re-implementation)", "walk": "random walk with restart on call graph (PyRCA/RCD-style, simplified)",
           "errors": "error-ratio z only (naive)", "random": "random"}


def anomaly_scores(rows: pd.DataFrame, cols=Z_COLS) -> dict:
    out = {}
    for s in SERVICES:
        v = [abs(rows.loc[s, c]) for c in cols if s in rows.index and c in rows.columns and np.isfinite(rows.loc[s, c])]
        out[s] = max(v) if v else 0.0
    return out


def rank_baro(scores: dict) -> list:
    return sorted(scores, key=lambda s: (-scores[s], s))


def rank_walk(scores: dict, restart=0.15, iters=100) -> list:
    """Random walk with restart on the undirected call graph. Moves toward neighbours in proportion to their anomaly score;
    restarts in proportion to the node's own anomaly score. Visit frequency ranks the candidates."""
    idx = {s: i for i, s in enumerate(SERVICES)}
    n = len(SERVICES)
    w = np.zeros((n, n))
    for a, callees in TOPOLOGY.items():
        for b in callees:
            w[idx[a], idx[b]] = w[idx[b], idx[a]] = 1.0
    a_vec = np.array([scores[s] for s in SERVICES]) + 1e-6
    trans = w * a_vec[None, :]
    trans = trans / trans.sum(axis=1, keepdims=True)
    restart_vec = a_vec / a_vec.sum()
    p = np.full(n, 1.0 / n)
    for _ in range(iters):
        p = (1 - restart) * (p @ trans) + restart * restart_vec
    return sorted(SERVICES, key=lambda s: (-p[idx[s]], s))


def rank_errors(rows: pd.DataFrame) -> list:
    sc = {s: abs(rows.loc[s, "error_ratio_z"]) if s in rows.index and np.isfinite(rows.loc[s, "error_ratio_z"]) else 0.0 for s in SERVICES}
    return sorted(sc, key=lambda s: (-sc[s], s))


def incidents(df: pd.DataFrame):
    """Yield (run, scenario, rel, target, per-service rows) with the same definition as train_models.py's ranker table."""
    fault = df[~df.scenario.isin(HEALTHY_SCEN)]
    for run, g in fault.groupby("run"):
        for rel in DELAYS:
            at = g[(g.rel >= rel - 1) & (g.rel <= rel + 1)]
            if at.service.nunique() < len(SERVICES):
                continue
            yield run, g.scenario.iloc[0], rel, g.target.iloc[0], at.groupby("service").first()


def evaluate(df: pd.DataFrame) -> pd.DataFrame:
    recs = []
    for run, scen, rel, tgt, rows in incidents(df):
        sc = anomaly_scores(rows)
        order = {"baro": rank_baro(sc), "walk": rank_walk(sc), "errors": rank_errors(rows),
                 "random": list(np.random.default_rng(zlib.crc32(f"{run}{rel}".encode())).permutation(SERVICES))}
        for m, o in order.items():
            recs.append({"run": run, "scenario": scen, "rel": rel, "target": tgt, "method": m,
                         "top1": float(o[0] == tgt), "top3": float(tgt in o[:3])})
    return pd.DataFrame(recs)


def pooled_by_run(res: pd.DataFrame, col: str, n=2000, seed=0):
    """Mean over incidents with a bootstrap 95% interval that resamples whole runs."""
    per = res.groupby("run")[col].agg(["sum", "count"])
    rng = np.random.default_rng(seed)
    means = []
    for _ in range(n):
        pick = rng.integers(0, len(per), len(per))
        means.append(per["sum"].values[pick].sum() / per["count"].values[pick].sum())
    return per["sum"].sum() / per["count"].sum(), float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def render(res: pd.DataFrame, fixture=False) -> str:
    R = ["# Offline root-cause baselines (training runs)\n"]
    if fixture:
        R.append("> **FIXTURE DATA, NOT RESULTS.**\n")
    R.append("**OFFLINE comparison on the training runs. Not a live arm, not a benchmark result.** Methods are untrained and re-implemented (not the RCAEval or PyRCA packages); "
             "intervals are bootstrap 95% resampling whole runs. The learned ranker's out-of-fold figure is in `docs/results/models_cv.md` (same incident definition) and is not recomputed here. "
             "RE2/RE3 were not downloaded.\n")
    R.append(f"Runs: {res.run.nunique()}; incidents per method: {len(res[res.method == 'random'])}.\n")
    R.append("| method | top-1 [95%] | top-3 [95%] |\n|---|---|---|")
    for m, label in METHODS.items():
        r = res[res.method == m]
        a, b = pooled_by_run(r, "top1"), pooled_by_run(r, "top3")
        R.append(f"| {label} | {a[0]:.3f} [{a[1]:.3f}, {a[2]:.3f}] | {b[0]:.3f} [{b[1]:.3f}, {b[2]:.3f}] |")
    R.append("\n## Top-1 by fault scenario\n")
    tab = res.pivot_table(index="scenario", columns="method", values="top1", aggfunc="mean").round(3)
    tab["incidents"] = res[res.method == "random"].groupby("scenario").size()
    R.append(tab.reset_index().to_markdown(index=False))
    return "\n".join(R) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", default=str(ROOT / "data" / "runs"))
    ap.add_argument("--out", default=str(ROOT / "docs" / "results" / "offline_rca_baseline.md"))
    a = ap.parse_args()
    import train_models as tm
    runs, excluded = tm.load_runs(a.runs)
    df = tm.build_rows(runs, tm.make_baselines(runs))
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(render(evaluate(df)), encoding="utf-8")
    print(f"wrote {a.out} from {len(runs)} runs ({len(excluded)} excluded)")


if __name__ == "__main__":
    main()
