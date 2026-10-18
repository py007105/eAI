"""Post-mortem helper (read-only, offline): what do the FROZEN models-v1 say about crash windows, by target service?

    python scripts/postmortem_crash_classifier.py --runs D:/eAI/eAI-workspace/eAI/data/runs [--out docs/postmortems/crash-classifier-by-target.md]

For each training crash run, build the same feature windows the live brain uses (train_models.build_rows), 10-40 s after injection, and apply the
frozen classifier + novelty gate (artifacts/classifier.joblib). CAVEAT: these runs are IN the training data of the frozen models, so this shows what the
models do on crash windows they were trained on, not a generalisation estimate. The benchmark rows themselves hold no feature windows, so the benchmark
crashes (seeds 100 and 120 on orders) cannot be replayed; this is a proxy and is labelled as such.
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "models"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", required=True)
    ap.add_argument("--out", default=str(ROOT / "docs" / "postmortems" / "crash-classifier-by-target.md"))
    a = ap.parse_args()
    import train_models as tm
    from eternalai import artifacts
    cls, meta = artifacts.load("classifier")
    runs, _ = tm.load_runs(a.runs)
    runs = [r for r in runs if r["truth"]["scenario"] == "crash"]
    df = tm.build_rows(runs, tm.make_baselines(tm.load_runs(a.runs)[0]))
    df = df[(df.label == "crash") | (df.service == df.target)]
    out = []
    for run, g in df[df.service == df.target].groupby("run"):
        for rel_lo, rel_hi in ((10, 20), (20, 30), (30, 40)):
            w = g[(g.rel >= rel_lo) & (g.rel < rel_hi)]
            preds = [cls.predict(r.to_dict()) for _, r in w.iterrows()]
            if not preds:
                continue
            out.append({"run": run, "target": g.target.iloc[0], "rel_s": f"{rel_lo}-{rel_hi}", "windows": len(preds),
                        "answered": sum(not p.abstained for p in preds), "abstain_novel": sum(p.reason == "novel" for p in preds),
                        "abstain_low_conf": sum(p.reason == "low_confidence" for p in preds),
                        "top labels": dict(pd.Series([p.label for p in preds]).value_counts()),
                        "median novelty": round(float(np.nanmedian([p.novelty for p in preds])), 3) if preds[0].novelty is not None else None})
    thr = getattr(cls.gate, "threshold_", None)
    text = ["# Frozen classifier on training crash windows, by target (offline proxy, IN-SAMPLE)\n",
            "Read-only replay of `models-v1` on the training crash runs. These runs are part of the models' training data, so this is not a generalisation estimate; "
            "the benchmark rows hold no feature windows, so the benchmark's own orders-crash runs cannot be replayed. "
            f"Novelty threshold in force: {thr}. Abstain-below confidence: {cls.abstain_below}.\n",
            pd.DataFrame(out).to_markdown(index=False), ""]
    Path(a.out).write_text("\n".join(text), encoding="utf-8")
    print("\n".join(text))


if __name__ == "__main__":
    main()
