"""Turn RCAEval RE1 cases into feature rows with the shared window code.

    python data/build_rcaeval_features.py [--raw data/raw] [--out data/processed/rcaeval_re1_features.csv]

Per case and service:
 * baseline = healthy median/MAD fitted on the FIRST half of that service's pre-injection data
   (per-service normalisation; same thing the live system does from its own healthy history);
 * a fault row = window ending `--delay` seconds after injection (simulates detection delay);
 * a healthy row = window ending at the end of pre-injection data (no overlap with the baseline half).
Label columns are written separately from features so they cannot be fed to a model by accident.
"""
import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from eternalai.features.window import fit_baseline, window_features  # noqa: E402
from rcaeval_loader import iter_cases  # noqa: E402

FAULT_LABEL = {"cpu": "cpu_saturation", "mem": "memory_leak", "delay": "network_delay",
               "loss": "packet_loss", "disk": "disk_io_pressure"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default="data/raw")
    ap.add_argument("--out", default="data/processed/rcaeval_re1_features.csv")
    ap.add_argument("--delay", type=int, default=60)
    ap.add_argument("--window", type=float, default=30.0)
    a = ap.parse_args()
    rows = []
    for case in iter_cases(a.raw):
        for svc, d in case.signals.items():
            pre = d[d.index < case.inject_time]
            if len(pre) < 120:
                continue
            half = pre.index[len(pre) // 2]
            base = fit_baseline(pre[pre.index < half])
            meta = {"case_id": case.case_id, "system": case.system, "service": svc,
                    "root_service": case.root_service, "rep": case.rep}
            end_fault = case.inject_time + a.delay
            wf = d[(d.index <= end_fault)]
            rows.append({**meta, "window": "fault", "fault": FAULT_LABEL[case.fault],
                         "is_root": int(svc == case.root_service),
                         **window_features(wf, base, a.window)})
            wh = pre[pre.index >= half]
            rows.append({**meta, "window": "healthy", "fault": "healthy", "is_root": 0,
                         **window_features(wh, base, a.window)})
    out = pd.DataFrame(rows)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(a.out, index=False)
    print(f"{len(out)} rows, {out.case_id.nunique()} cases -> {a.out}")
    print(out.groupby(["system", "window"]).size().unstack())


if __name__ == "__main__":
    main()
