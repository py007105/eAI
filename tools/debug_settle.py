"""Debug helper: when does the stack become clean after a restore? Pooled error ratio and missing-rate fraction per
5-second bin of time-before-injection, across all runs (web, orders, inventory, payments).

    python tools/debug_settle.py
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

runs = Path("ml/data/runs")
rows = []
for js in sorted(runs.glob("*.json")):
    if js.name == "EXCLUDED.json":
        continue
    t0 = json.loads(js.read_text())["t_inject"]
    raw = pd.read_csv(js.with_suffix(".csv"), index_col=[0, 1])
    for svc in raw.index.get_level_values(0).unique():
        f = raw.loc[svc]
        f = f[(f.index >= t0 - 110) & (f.index < t0)]
        for t, r in f.iterrows():
            rows.append((js.stem, svc, t - t0, r.get("req_rate"), r.get("err_rate"), r.get("up")))
d = pd.DataFrame(rows, columns=["run", "svc", "rel", "req", "err", "up"])
d["bin"] = (np.floor(d.rel / 5) * 5).astype(int)
g = d.groupby("bin")
out = pd.DataFrame({"error_ratio": g.err.sum() / g.req.sum(),
                    "frac_samples_with_errors": g.err.apply(lambda s: float((s.fillna(0) > 0).mean())),
                    "frac_req_missing": g.req.apply(lambda s: float(s.isna().mean())),
                    "frac_not_up": g.up.apply(lambda s: float((s.fillna(0) < 1).mean()))})
print(out.round(3).to_string())
