"""Debug helper: how do feature values evolve after injection for window lengths 10/20/30 s?

    python tools/debug_windows.py crash_1000 error_spike_1002
Shows the target service's features at several offsets after the injection, per window length.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine.features.window import fit_baseline, window_features  # noqa: E402

runs = Path("ml/data/runs")
SHOW = ["up_frac", "error_ratio", "lat_ratio", "cpu_per_req_ratio", "mem_share", "dep_fail_rate"]
for rid in sys.argv[1:]:
    truth = json.loads((runs / f"{rid}.json").read_text())
    raw = pd.read_csv(runs / f"{rid}.csv", index_col=[0, 1])
    t0, tg = truth["t_inject"], truth["target"]
    df = raw.loc[tg].dropna(axis=1, how="all")
    base = fit_baseline(df[df.index < t0 - 60])
    print(f"\n== {rid} (target {tg}); data ends at rel {df.index.max() - t0:.0f} s")
    for win in (10, 20, 30):
        rows = []
        for rel in (-10, 6, 10, 14, 20, 26, 32):
            end = t0 + rel
            w = df[(df.index <= end) & (df.index > end - 150)]
            if len(w) < 20 or end > df.index.max():
                continue
            f = window_features(w, base, win)
            rows.append({"rel": rel, **{k: round(f[k], 3) if np.isfinite(f[k]) else None for k in SHOW}})
        print(f"-- window {win} s")
        print(pd.DataFrame(rows).to_string(index=False))
