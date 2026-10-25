"""Read-only diagnosis of the healthy-surge false alarms (G2). Offline, on the existing training runs; nothing is retrained or changed.

    python tools/diag_surge.py --runs D:/eAI/eAI-workspace/eAI/data/runs [--out docs/postmortems/surge-diagnosis-data.md]

What it measures (all IN-SAMPLE for the frozen models-v1: the training surge runs are part of the models' training data, so this shows what the models
learned about surges, not how they generalise; the benchmark rows hold no feature windows):
  1. traffic variation in the training data: surge parameters, targets, durations, and the request rate each service saw (pre-injection vs surge);
  2. how each frozen detector and the classifier treat the surge windows, per service (flagged share, classifier labels, which learned limits were exceeded);
  3. memory: per-service memory (relative to its healthy baseline) before and during surge, because the live incidents were diagnosed `memory_leak` on `inventory`;
  4. which model inputs are traffic-normalised and which are not.
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "ml" / "models"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", required=True)
    ap.add_argument("--out", default=str(ROOT / "docs" / "postmortems" / "surge-diagnosis-data.md"))
    a = ap.parse_args()
    import train_models as tm
    from engine import artifacts
    from engine.features.window import FEATURE_NAMES
    runs, _ = tm.load_runs(a.runs)
    base = tm.make_baselines(runs)
    det, _ = artifacts.load("detectors")
    cls, _ = artifacts.load("classifier")
    R = ["# Surge diagnosis, data side (offline, in-sample for models-v1)\n"]

    surge_runs = [r for r in runs if r["truth"]["scenario"] == "traffic_surge"]
    R.append("## 1. Traffic variation in the training ml\data\n")
    rows = []
    for r in surge_runs:
        t0 = r["truth"]["t_inject"]
        row = {"run": r["id"], "target": r["truth"]["target"], "params": str(r["truth"]["params"])}
        for s, df in r["frames"].items():
            pre, dur = df[(df.index >= t0 - 40) & (df.index < t0 - 5)], df[(df.index >= t0 + 10) & (df.index < t0 + 40)]
            row[f"{s} rps pre->surge"] = f"{pre.req_rate.mean():.1f}->{dur.req_rate.mean():.1f}"
        rows.append(row)
    R.append(pd.DataFrame(rows).to_markdown(index=False))
    R.append(f"\nDistinct surge parameter sets in training: {sorted({x['params'] for x in rows})}; targets: {sorted({x['target'] for x in rows})}; runs: {len(rows)}. "
             "The evaluator's surge lasts 40 s (`evaluator/scenarios.py`).\n")

    df = tm.build_rows(surge_runs, base)
    df = df[df.rel.between(5, 40)]
    flags, score = tm.det_flags(det, df)
    df = df.assign(flag=flags, score=score)
    R.append("## 2. Frozen detector and classifier on the training surge windows (5-40 s after injection)\n")
    rows = []
    for s, g in df.groupby("service"):
        preds = [cls.predict(r.to_dict()) for _, r in g.iterrows()]
        lab = pd.Series([p.label for p in preds]).value_counts().to_dict()
        over = {}
        for f, (lo, hi) in det[s].limits.items():
            v = g[f].astype(float)
            n = int(((v > hi) | ((v < lo) if f in tm.TWO_SIDED else False)).sum())
            if n:
                over[f] = n
        rows.append({"service": s, "windows": len(g), "detector flagged": f"{int(g.flag.sum())} ({g.flag.mean():.0%})",
                     "classifier labels": {k: int(v) for k, v in lab.items()}, "limit exceedances (feature: windows)": over})
    R.append(pd.DataFrame(rows).to_markdown(index=False))

    R.append("\n## 3. Memory relative to the healthy baseline, before and during the surge (median over training surge runs)\n")
    rows = []
    for s in ("web", "orders", "inventory", "payments"):
        pre = df_all = None
        pre_v, dur_v = [], []
        for r in surge_runs:
            f = r["frames"].get(s)
            if f is None:
                continue
            t0 = r["truth"]["t_inject"]
            b = base[s]
            m_pre = f[(f.index >= t0 - 40) & (f.index < t0 - 5)].mem_bytes.median()
            m_dur = f[(f.index >= t0 + 10) & (f.index < t0 + 40)].mem_bytes.median()
            pre_v.append(m_pre / 1e6)
            dur_v.append(m_dur / 1e6)
        rows.append({"service": s, "median MB before": round(float(np.nanmedian(pre_v)), 1), "median MB during surge": round(float(np.nanmedian(dur_v)), 1),
                     "runs": len(pre_v)})
    R.append(pd.DataFrame(rows).to_markdown(index=False))

    R.append("\n## 5. Memory-related features on surge windows versus the learned healthy limits\n")
    rows = []
    for s, g in df.groupby("service"):
        lim = det[s].limits
        for f in ("mem_slope_share_per_min", "mem_ratio", "mem_z", "mem_share"):
            if f in g and f in lim:
                v = g[f].astype(float)
                rows.append({"service": s, "feature": f, "surge windows: median": round(float(v.median()), 4), "p95": round(float(v.quantile(0.95)), 4),
                             "max": round(float(v.max()), 4), "learned limit (hi)": round(float(lim[f][1]), 4)})
    R.append(pd.DataFrame(rows).to_markdown(index=False) if rows else "no memory feature is among the learned limits (keys: " + ", ".join(det["inventory"].limits) + ")")
    R.append("\nThe rule baseline (`engine/classify.py::rule_diagnose`, used by the prototype_rules arm) says `memory_leak` when `mem_share > 0.8` or `mem_slope_share_per_min > 0.05`.")

    R.append("\n## 6. Does a service's healthy memory drift with uptime/run order? (pre-injection median memory per training run, in seed order)\n")
    rows = []
    allruns = sorted(runs, key=lambda r: r["truth"]["seed"])
    for s in ("inventory", "web"):
        mb = [(r["truth"]["seed"], r["frames"][s][(r["frames"][s].index >= r["truth"]["t_inject"] - 40) & (r["frames"][s].index < r["truth"]["t_inject"] - 5)].mem_bytes.median() / 1e6)
              for r in allruns if s in r["frames"]]
        mb = [(a_, b_) for a_, b_ in mb if np.isfinite(b_)]
        seeds, vals = np.array([x[0] for x in mb], float), np.array([x[1] for x in mb])
        slope = np.polyfit(seeds, vals, 1)[0] * 100 if len(vals) > 3 else float("nan")
        lim_mb = (det[s].limits.get("mem_share", (0, float("nan")))[1]) * 268.435456
        rows.append({"service": s, "runs": len(vals), "pre-injection MB min": round(float(vals.min()), 1), "median": round(float(np.median(vals)), 1),
                     "max": round(float(vals.max()), 1), "MB per 100 seeds (linear fit)": round(float(slope), 2),
                     "learned mem_share limit as MB (of 256 MiB)": round(float(lim_mb), 1)})
    R.append(pd.DataFrame(rows).to_markdown(index=False))
    R.append("\nThe learned `mem_share` limit sits a few MB above the largest healthy memory seen in training. A service whose healthy memory is a little higher in a longer-lived container "
             "(or that allocates a few MB more under load) is outside the learned healthy range. This is a hypothesis about the live behaviour; the benchmark rows hold no memory series to test it.")

    R.append("\n## 4. Model inputs: traffic-normalised or not\n")
    norm = [f for f in FEATURE_NAMES if "per_req" in f]
    R.append(f"Classifier inputs ({len(FEATURE_NAMES)}): " + ", ".join(FEATURE_NAMES) + ".\n")
    R.append(f"Names containing `per_req` (explicitly divided by request rate): {norm}. Everything else is a ratio or z-score against the service's own healthy baseline, "
             "which does not remove a change in request rate; `rps_ratio` and `rps_z` are themselves inputs, so the models can see the surge. Memory features (`mem_*`) are not normalised for traffic.")
    Path(a.out).write_text("\n".join(R) + "\n", encoding="utf-8")
    print("\n".join(R))


if __name__ == "__main__":
    main()
