"""Debug helper: IsolationForest scores on healthy versus fault windows for one CV fold (window 10 s).

    python scripts/debug_detector.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "models"))
import train_models as tm  # noqa: E402

runs, _ = tm.load_runs("data/runs")
df = tm.build_rows(runs, tm.make_baselines(runs), 10.0)
tr_runs, te_runs = next(iter(tm.folds(df, 5, 0)))
tr, te = df[df.run.isin(tr_runs)], df[df.run.isin(te_runs)].copy()
det = tm.fit_detectors(tr, 0)
te["anom"], te["score"] = tm.det_flags(det, te)
print("per-service threshold:", {s: round(d.threshold, 3) for s, d in det.items()})
h = te[te.label == "healthy"]
print("healthy score quantiles (all services):", h.score.quantile([.5, .9, .99, .999]).round(3).to_dict())
for s in tm.config.SERVICES:
    hs = h[h.service == s]
    print(f"  {s}: healthy median {hs.score.median():.3f}, p99 {hs.score.quantile(.99):.3f}, flagged {hs.anom.mean():.3f}")
for scen in ("bad_deploy", "error_spike", "latency", "memory_leak", "disk_fill"):
    f = te[(te.scenario == scen) & (te.service == te.target) & (te.rel >= 10) & (te.rel <= 60)]
    if f.empty:
        continue
    print(f"\n{scen}: n={len(f)}, score median {f.score.median():.3f}, max {f.score.max():.3f}, flagged {f.anom.mean():.2f}")
    print(f[tm.DET_FEATURES].median().round(3).to_dict())
print("\nhealthy feature medians:", h[tm.DET_FEATURES].median().round(3).to_dict())
