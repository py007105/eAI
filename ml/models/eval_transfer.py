"""Does anything beat the current cross-system model on RCAEval RE1? Honest leave-one-system-out test.

    python ml/models/eval_transfer.py [--features ml/data/processed/rcaeval_re1_features.csv]
                                   [--out docs/results/transfer_re1.md] [--boot 500]

Variants (all evaluated leave-one-system-out; majority class and logistic regression alongside):
  raw        current features, no normalisation (the model to beat)
  sysnorm    each system's features standardised with the median/MAD of THAT system's own healthy rows
             (what a live deployment can do from its own healthy history; no fault rows are used)
  dropid     greedy removal of the features that best identify the system, chosen by inner
             leave-one-system-out CV on the TRAINING systems only
  sysnorm+dropid  both
Selection (which features to drop) never sees the held-out system. Confidence intervals come from
bootstrapping whole incidents within each held-out system.
"""
import argparse
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from engine.safe_model import SafeHGB  # noqa: E402
from eval_rcaeval import load  # noqa: E402

POOL = ["rps_ratio", "rps_z", "lat_ratio", "lat_z", "cpu_ratio", "cpu_z", "mem_ratio", "mem_z", "error_ratio_z",
        "cpu_per_req_ratio", "cpu_per_req_z"]
ORIG9 = ["rps_ratio", "rps_z", "lat_ratio", "lat_z", "cpu_ratio", "cpu_z", "mem_ratio", "mem_z", "error_ratio_z"]
MIN_FEATURES = 3


def hgb(seed=0):
    return SafeHGB(max_depth=3, max_iter=100, learning_rate=0.05, min_samples_leaf=20,
                                          l2_regularization=1.0, class_weight="balanced", random_state=seed)


def logreg():
    return make_pipeline(SimpleImputer(strategy="median"), StandardScaler(),
                         LogisticRegression(C=0.1, max_iter=2000, class_weight="balanced"))


def mf1(y, p):
    return f1_score(y, p, average="macro", labels=sorted(set(y)), zero_division=0)


def system_normalise(d: pd.DataFrame, cols) -> pd.DataFrame:
    """Per-system robust standardisation using that system's own healthy rows only."""
    out = d.copy()
    for s, g in d.groupby("system"):
        h = g[g.fault == "healthy"][cols]
        med = h.median()
        mad = (h - med).abs().median() * 1.4826
        mad = mad.where(mad > 1e-6, h.std().where(h.std() > 1e-6, 1.0))
        out.loc[g.index, cols] = (g[cols] - med) / mad
    return out


def probe_f1(X, systems, groups, seed=0):
    """Macro-F1 of predicting WHICH SYSTEM a row came from (grouped CV): lower = less identifying."""
    if len(set(systems)) < 2:
        return float("nan")
    sc = []
    n = min(5, len(set(groups)) // 2) or 2
    for tri, tei in StratifiedGroupKFold(n, shuffle=True, random_state=seed).split(X, systems, groups):
        m = hgb(seed).fit(X[tri], systems[tri])
        sc.append(mf1(systems[tei], m.predict(X[tei])))
    return float(np.mean(sc))


def inner_loso(d: pd.DataFrame, cols) -> float:
    """Inner leave-one-system-out over the TRAINING systems only."""
    sc = []
    for s in d.system.unique():
        tr, te = d[d.system != s], d[d.system == s]
        if tr.empty or te.empty:
            continue
        m = hgb().fit(tr[cols].values, tr.fault.values)
        sc.append(mf1(te.fault.values, m.predict(te[cols].values)))
    return float(np.mean(sc))


def select_features(train: pd.DataFrame, cols, tolerance=0.02):
    """Greedy backward elimination of identity-bearing features, judged on the training systems only.

    Each step removes the feature whose removal lowers the system probe the most while the inner
    leave-one-system-out fault F1 stays within `tolerance` of the best seen."""
    cols = list(cols)
    best_inner = inner_loso(train, cols)
    cur_probe = probe_f1(train[cols].values, train.system.values, train.case_id.values)
    keep = list(cols)
    while len(keep) > MIN_FEATURES:
        cands = []
        for c in keep:
            rest = [k for k in keep if k != c]
            inner = inner_loso(train, rest)
            if inner >= best_inner - tolerance:
                cands.append((probe_f1(train[rest].values, train.system.values, train.case_id.values), inner, c))
        if not cands:
            break
        p, inner, c = min(cands)
        if p >= cur_probe - 1e-9:
            break
        keep.remove(c)
        cur_probe, best_inner = p, max(best_inner, inner)
    return keep


def run_variant(d, pool, variant, model_fn, seed=0):
    """Leave-one-system-out predictions for one variant. Returns {system: DataFrame(case_id, y, p)}."""
    out = {}
    base = system_normalise(d, pool) if "sysnorm" in variant else d
    for s in sorted(d.system.unique()):
        tr, te = base[base.system != s], base[base.system == s]
        cols = select_features(tr, pool) if "dropid" in variant else pool
        m = model_fn(seed) if model_fn is hgb else model_fn()
        m.fit(tr[cols].values, tr.fault.values)
        out[s] = pd.DataFrame({"case_id": te.case_id.values, "y": te.fault.values, "p": m.predict(te[cols].values),
                               "cols": [",".join(cols)] * len(te)})
    return out


def score(preds):
    return {s: mf1(g.y.values, g.p.values) for s, g in preds.items()}


def boot_ci(preds_by_variant, ref, n_boot, seed=0):
    """Bootstrap by incident within each held-out system. Returns mean-F1 CI per variant and delta-vs-ref CI."""
    rng = np.random.default_rng(seed)
    systems = sorted(preds_by_variant[ref])
    idx = {s: {v: preds_by_variant[v][s].groupby("case_id").indices for v in preds_by_variant} for s in systems}
    res = {v: [] for v in preds_by_variant}
    for _ in range(n_boot):
        pick = {}
        for s in systems:
            cases = np.array(list(idx[s][ref]))
            pick[s] = rng.choice(cases, len(cases), replace=True)
        for v, P in preds_by_variant.items():
            f = []
            for s in systems:
                g = P[s]
                ix = np.concatenate([idx[s][v][c] for c in pick[s]])
                f.append(mf1(g.y.values[ix], g.p.values[ix]))
            res[v].append(np.mean(f))
    out = {}
    for v, arr in res.items():
        arr = np.array(arr)
        delta = arr - np.array(res[ref])
        out[v] = {"mean": float(np.mean(arr)), "ci": tuple(np.percentile(arr, [2.5, 97.5])),
                  "delta_ci": tuple(np.percentile(delta, [2.5, 97.5]))}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--features", default="ml/data/processed/rcaeval_re1_features.csv")
    ap.add_argument("--out", default="docs/results/transfer_re1.md")
    ap.add_argument("--boot", type=int, default=500)
    a = ap.parse_args()
    warnings.filterwarnings("ignore")
    d = load(a.features).reset_index(drop=True)
    pool = [c for c in POOL if c in d and d[c].notna().mean() >= 0.25 and d[c].nunique() >= 20]
    R = ["# Cross-system transfer experiments (RCAEval RE1, leave-one-system-out)\n",
         "Generated by `ml/models/eval_transfer.py`. Feature subsets are chosen from the TRAINING systems only; "
         "the held-out system is used neither for selection nor for model fitting. "
         "Normalisation statistics for a system come from that system's own healthy rows (no fault rows).\n",
         f"- rows: {len(d)}; incidents: {d.case_id.nunique()}; candidate features: {pool}",
         f"- bootstrap resamples (whole incidents, within each held-out system): {a.boot}\n"]

    variants = {"raw": "raw", "sysnorm": "sysnorm", "dropid": "dropid", "sysnorm+dropid": "sysnorm+dropid"}
    preds = {}
    orig = [c for c in ORIG9 if c in pool]
    # the model currently in use: the original 9 features, no normalisation (the number reported as 0.616)
    preds["current model: raw / hgb, original 9 features"] = run_variant(d, orig, "raw", hgb)
    for name, v in variants.items():
        preds[f"{name} / hgb"] = run_variant(d, pool, v, hgb)
    preds["raw / logreg"] = run_variant(d, pool, "raw", logreg)
    preds["sysnorm / logreg"] = run_variant(d, pool, "sysnorm", logreg)
    maj = {}
    for s in sorted(d.system.unique()):
        tr, te = d[d.system != s], d[d.system == s]
        m = DummyClassifier(strategy="most_frequent").fit(tr[pool].values, tr.fault.values)
        maj[s] = pd.DataFrame({"case_id": te.case_id.values, "y": te.fault.values, "p": m.predict(te[pool].values)})
    preds["majority class"] = maj

    ref = "current model: raw / hgb, original 9 features"
    ci = boot_ci(preds, ref, a.boot)
    R.append("## Leave-one-system-out macro-F1\n")
    R.append("| variant | " + " | ".join(sorted(d.system.unique())) + " | mean | 95% CI of mean | delta vs current model (95% CI) |\n"
             "|---|" + "---|" * (len(d.system.unique()) + 3))
    for v, P in preds.items():
        sc = score(P)
        c = ci[v]
        R.append(f"| {v} | " + " | ".join(f"{sc[s]:.3f}" for s in sorted(sc)) + f" | {np.mean(list(sc.values())):.3f} | "
                 f"[{c['ci'][0]:.3f}, {c['ci'][1]:.3f}] | " +
                 ("reference" if v == ref else f"[{c['delta_ci'][0]:+.3f}, {c['delta_ci'][1]:+.3f}]") + " |")

    R.append("\n## Which features were kept (per held-out system; selected on the other two systems)\n")
    for name in ("dropid / hgb", "sysnorm+dropid / hgb"):
        for s, g in preds[name].items():
            R.append(f"- {name}, held out {s}: {g.cols.iloc[0]}")

    R.append("\n## System-identification probe (macro-F1 predicting the system; chance ≈ 0.33)\n")
    R.append("| feature set | probe F1 |\n|---|---|")
    full = d[pool].values
    R.append(f"| raw, all {len(pool)} features | {probe_f1(full, d.system.values, d.case_id.values):.3f} |")
    nd = system_normalise(d, pool)
    R.append(f"| sysnorm, all {len(pool)} features | {probe_f1(nd[pool].values, d.system.values, d.case_id.values):.3f} |")
    keep_raw = select_features(d, pool)
    R.append(f"| raw, dropid subset ({len(keep_raw)}: {keep_raw}) | {probe_f1(d[keep_raw].values, d.system.values, d.case_id.values):.3f} |")
    keep_n = select_features(nd, pool)
    R.append(f"| sysnorm + dropid subset ({len(keep_n)}: {keep_n}) | {probe_f1(nd[keep_n].values, d.system.values, d.case_id.values):.3f} |")
    R.append("\n(The subsets in the last two rows are selected on all three systems purely to report the probe; "
             "they are not used for any held-out score above.)")

    point = {v: float(np.mean(list(score(P).values()))) for v, P in preds.items()}  # same numbers as the table
    best = max((v for v in preds if v != "majority class"), key=lambda v: point[v])
    sig = [v for v in preds if v != ref and ci[v]["delta_ci"][0] > 0]
    R.append("\n## Verdict\n")
    if sig:
        R.append(f"- Variants whose improvement over the current model has a 95% CI above zero: {sig}.")
    else:
        R.append("- No variant improves on the current model with a 95% confidence interval above zero. The current model is kept.")
    R.append(f"- Highest mean macro-F1: {best} ({point[best]:.3f}); this is a point estimate, and its interval overlaps the "
             f"current model's, so it is not evidence of an improvement.")

    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text("\n".join(R) + "\n", encoding="utf-8")
    print("\n".join(R))


if __name__ == "__main__":
    main()
