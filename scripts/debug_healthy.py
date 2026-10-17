"""Debug helper: which windows labelled 'healthy' have extreme detector features, and from which scenarios?

    python scripts/debug_healthy.py
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
h = df[df.label == "healthy"].copy()
h["phase"] = np.where(h.rel <= -5, "pre-injection", "post-injection (healthy scenarios)")
print("healthy windows:", len(h), h.groupby(["phase", "scenario"]).size().to_dict())
for f in ["error_ratio", "lat_ratio", "error_log_rate", "cpu_per_req_ratio", "mem_share"]:
    print(f"\n{f}: quantiles {h[f].quantile([.5, .99, .999]).round(3).to_dict()}, max {h[f].max():.3f}")
    hot = h[h[f] > (0.05 if f == "error_ratio" else h[f].quantile(.999))]
    print("  windows above that:", hot.groupby(["phase", "scenario"]).size().to_dict())
big = h[h.error_ratio > 0.05]
print("\nwindows with error_ratio > 0.05:", len(big), "| by phase/scenario/service:")
print(big.groupby(["phase", "scenario", "service"]).size().to_string())
sv = h[(h.scenario == "traffic_surge") & (h.rel >= 10)]
print("\ntraffic_surge post-onset windows (web): error_ratio quantiles", sv[sv.service == "web"].error_ratio.quantile([.5, .9, .99]).round(3).to_dict(),
      "| lat_ratio", sv[sv.service == "web"].lat_ratio.quantile([.5, .9]).round(2).to_dict())
