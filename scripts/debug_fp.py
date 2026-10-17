"""Debug helper: where do the detector's false alarms on healthy windows come from? (out-of-fold, all 5 folds)

    python scripts/debug_fp.py
Splits each flagged healthy window into: 'not scraped' rule, IsolationForest score, learned limits (per feature),
and reports by phase (pre-injection versus healthy-scenario post-injection), scenario and service.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "models"))
import train_models as tm  # noqa: E402
from eternalai.detect import TWO_SIDED  # noqa: E402

runs, _ = tm.load_runs("data/runs")
df = tm.build_rows(runs, tm.make_baselines(runs), 10.0)
parts = []
for k, (tr_runs, te_runs) in enumerate(tm.folds(df, 5, 0)):
    tr, te = df[df.run.isin(tr_runs)], df[df.run.isin(te_runs)].copy()
    det = tm.fit_detectors(tr, seed=k)
    te["f_up"] = ((te.up_frac == 0) | te.up_frac.isna()).values
    te["f_if"] = False
    for s, d in det.items():
        m = (te.service == s).values
        te.loc[m, "f_if"] = (-d.model.score_samples(te.loc[m, tm.DET_FEATURES].values)) > d.threshold
        for f, (lo, hi) in d.limits.items():
            v = te.loc[m, f].values.astype(float)
            with np.errstate(invalid="ignore"):
                te.loc[m, "lim_" + f] = (v > hi) | ((v < lo) if f in TWO_SIDED else False)
    parts.append(te)
o = pd.concat(parts)
lim_cols = [c for c in o.columns if c.startswith("lim_")]
o[lim_cols] = o[lim_cols].fillna(False).astype(bool)
o["f_lim"] = o[lim_cols].any(axis=1)
o["any"] = o.f_up | o.f_if | o.f_lim
h = o[o.label == "healthy"].copy()
h["phase"] = np.where(h.rel < 0, "pre-injection", "healthy-scenario post-injection")
print(f"healthy windows {len(h)}; flagged {int(h['any'].sum())} ({h['any'].mean():.3f})")
print("by component (a window can have several): not-scraped rule", int(h.f_up.sum()), "| IsolationForest", int(h.f_if.sum()),
      "| learned limits", int(h.f_lim.sum()))
print("limits by feature:", {c[4:]: int(h[c].sum()) for c in lim_cols if h[c].sum()})
print("\nflagged share by phase:", h.groupby("phase")["any"].mean().round(3).to_dict())
print("flagged share by service (pre-injection):", h[h.phase == "pre-injection"].groupby("service")["any"].mean().round(3).to_dict())
print("flagged share by scenario (pre-injection):", h[h.phase == "pre-injection"].groupby("scenario")["any"].mean().round(3).to_dict())
print("flagged share by scenario (post, healthy scenarios):", h[h.phase != "pre-injection"].groupby("scenario")["any"].mean().round(3).to_dict())
print("\nIsolationForest-only flags by service x phase:")
print(h[h.f_if & ~h.f_lim & ~h.f_up].groupby(["phase", "service"]).size().to_string())
fl = h[h["any"]]
print("\nfeature medians of flagged vs unflagged healthy windows:")
print(pd.DataFrame({"flagged": fl[tm.DET_FEATURES].median(), "unflagged": h[~h["any"]][tm.DET_FEATURES].median()}).round(3).to_string())
print("\nrestarts_in_window / deploys_3m among flagged healthy windows:", fl.restarts_in_window.value_counts(dropna=False).to_dict(),
      fl.deploys_3m.value_counts(dropna=False).to_dict())
