"""Debug helper: one CV fold, window 10 s. Raw (uncalibrated) classifier recall, plus what latency and disk-fill
windows look like to the model.

    python scripts/debug_classifier.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "models"))
import train_models as tm  # noqa: E402

runs, excluded = tm.load_runs("data/runs")
base = tm.make_baselines(runs)
df = tm.build_rows(runs, base, 10.0)
tr_runs, te_runs = next(iter(tm.folds(df, 5, 0)))
tr, te = df[df.run.isin(tr_runs)], df[df.run.isin(te_runs)]
tk = te[tm.known_mask(te)].copy()
cls = tm.fit_classifier(tr, 0, calibrate=False)
tk["pred"], tk["conf"], _ = tm.predict(cls, tk)
print("raw recall:", {c: round(float((tk[tk.label == c].pred == c).mean()), 2) for c in tm.CLASSES if (tk.label == c).any()})
cols = ["rel", "lat_ratio", "error_ratio", "cpu_per_req_ratio", "up_frac", "error_log_rate", "mem_share", "pred"]
for lab in ("latency_spike", "disk_fill"):
    d = tk[tk.label == lab]
    print(f"\n{lab}: predicted as", d.pred.value_counts().to_dict())
    print(d[["run"] + cols].groupby("run").head(3).round(3).to_string(index=False))
print("\nhealthy-scenario latency baseline sanity: lat_ratio quantiles of healthy windows:",
      tk[tk.label == "healthy"].lat_ratio.quantile([.5, .9, .99]).round(2).to_dict())
