"""Train detector, classifier and root-cause ranker from live evaluator runs; evaluate without leakage.

    python models/train_models.py [--runs data/runs] [--out docs/results/models_cv.md] [--no-save]

* Split unit is the whole run (grouped, stratified by scenario); no window of a run is ever in both
  train and test. Calibration, abstain threshold and detector thresholds are chosen from
  held-out data, never on the training windows.
* cpu_burn is the UNSEEN fault: excluded from every training step, used only to test abstention.
* Healthy traffic surges and good deploys are labelled healthy (negatives).
* Every number printed here is what ends up in docs/results/models_cv.md.
"""
import argparse
import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import confusion_matrix, f1_score
from sklearn.model_selection import StratifiedGroupKFold

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from eternalai import artifacts, config  # noqa: E402
from eternalai.classify import ABSTAIN, CLASSES, FaultClassifier  # noqa: E402
from eternalai.detect import FEATURES as DET_FEATURES, fit_service  # noqa: E402
from eternalai.features.window import FEATURE_NAMES, fit_baseline, window_features  # noqa: E402
from eternalai.rca import EVIDENCE, Ranker, baro_rank, deepest_anomalous, evidence_table  # noqa: E402

warnings.filterwarnings("ignore")
HEALTHY_SCEN = {"traffic_surge", "good_deploy"}
CLS_FEATURES = [f for f in FEATURE_NAMES]


# ------------------------------------------------------------------ data
def load_runs(path):
    runs = []
    for js in sorted(Path(path).glob("*.json")):
        truth = json.loads(js.read_text())
        raw = pd.read_csv(js.with_suffix(".csv"), index_col=[0, 1])
        frames = {s: raw.loc[s].dropna(axis=1, how="all") if s in raw.index.get_level_values(0) else None
                  for s in config.SERVICES}
        runs.append({"id": js.stem, "truth": truth, "frames": {k: v for k, v in frames.items() if v is not None}})
    return runs


def make_baselines(runs):
    """Healthy-only per-service baseline: pre-injection data of all runs (contains no fault information)."""
    out = {}
    for s in config.SERVICES:
        pre = [r["frames"][s][r["frames"][s].index < r["truth"]["t_inject"] - 60] for r in runs if s in r["frames"]]
        out[s] = fit_baseline(pd.concat(pre))
    return out


def build_rows(runs, baselines):
    rows = []
    for r in runs:
        t0, tr = r["truth"]["t_inject"], r["truth"]
        for s, df in r["frames"].items():
            grid = np.arange(t0 - 110, min(t0 + 70, df.index.max()), 2.0)
            for end in grid:
                w = df[(df.index <= end) & (df.index > end - 150)]
                if len(w) < 20:
                    continue
                f = window_features(w, baselines[s])
                for k in ("depfail_inventory", "depfail_payments", "depfail_orders"):
                    f[k] = float(w[k].tail(5).mean()) if k in w else np.nan
                rel = end - t0
                if tr["scenario"] in HEALTHY_SCEN:
                    label = "healthy" if rel <= -5 or rel >= (20 if tr["scenario"] == "good_deploy" else 8) else "other"
                elif rel <= -5:
                    label = "healthy"
                elif rel >= 8 and s == tr["target"]:
                    label = tr["expected_label"]
                else:
                    label = "other"
                rows.append({"run": r["id"], "scenario": tr["scenario"], "target": tr["target"], "service": s,
                             "rel": rel, "end": end, "label": label, **f})
    return pd.DataFrame(rows)


def folds(runs_df, n=5, seed=0):
    runs = runs_df.drop_duplicates("run")[["run", "scenario"]].reset_index(drop=True)
    sgkf = StratifiedGroupKFold(n_splits=n, shuffle=True, random_state=seed)
    for tri, tei in sgkf.split(runs, runs.scenario, runs.run):
        yield set(runs.run[tri]), set(runs.run[tei])


# ------------------------------------------------------------------ detector
def fit_detectors(df, seed=0):
    """One IsolationForest per service on healthy rows; threshold from a held-out slice of healthy RUNS."""
    h = df[df.label == "healthy"]
    runs = sorted(h.run.unique())
    rng = np.random.default_rng(seed)
    val_runs = set(rng.choice(runs, max(2, len(runs) // 5), replace=False))
    det = {}
    for s in config.SERVICES:
        hs = h[h.service == s]
        tr, va = hs[~hs.run.isin(val_runs)], hs[hs.run.isin(val_runs)]
        det[s] = fit_service(tr[DET_FEATURES].values, va[DET_FEATURES].values, seed=seed)
    return det


def det_flags(det, df):
    out = np.zeros(len(df), dtype=bool)
    sc = np.full(len(df), np.nan)
    for s, d in det.items():
        m = (df.service == s).values
        sc[m] = -d.model.score_samples(df.loc[m, DET_FEATURES].values)
        out[m] = sc[m] > d.threshold
    # explicit rule: a service that is not scraped is anomalous (missing is not normal)
    out |= (df.up_frac == 0).values | df.up_frac.isna().values
    return out, sc


# ------------------------------------------------------------------ classifier
def fit_classifier(df, seed=0):
    d = df[(df.label.isin(CLASSES))]
    X, y, g = d[CLS_FEATURES].values, d.label.values, d.run.values
    base = HistGradientBoostingClassifier(max_depth=4, max_iter=150, learning_rate=0.06, min_samples_leaf=15,
                                          l2_regularization=1.0, class_weight="balanced", random_state=seed)
    inner = list(StratifiedGroupKFold(3, shuffle=True, random_state=seed).split(X, y, g))
    cal = CalibratedClassifierCV(base, method="sigmoid", cv=inner).fit(X, y)
    return cal


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", default="data/runs")
    ap.add_argument("--out", default="docs/results/models_cv.md")
    ap.add_argument("--no-save", action="store_true")
    a = ap.parse_args()
    runs = load_runs(a.runs)
    if len(runs) < 20:
        sys.exit(f"only {len(runs)} runs found; collect more with models/collect_runs.py")
    base = make_baselines(runs)
    df = build_rows(runs, base)
    R = ["# Model evaluation on live-stack runs (grouped CV by run)\n",
         "Generated by `models/train_models.py`. These are cross-validation numbers on TRAINING-seed runs "
         "(no-action runs). Final held-out numbers come from the evaluator with unseen seeds "
         "(see EVALUATION.md).\n",
         f"- runs: {len(runs)}; per scenario: {pd.Series([r['truth']['scenario'] for r in runs]).value_counts().to_dict()}",
         f"- window rows: {len(df)}; label counts: {df.label.value_counts().to_dict()}\n"]

    # ---- CV: detector + classifier
    oof = []
    for k, (tr_runs, te_runs) in enumerate(folds(df)):
        tr, te = df[df.run.isin(tr_runs)], df[df.run.isin(te_runs)].copy()
        assert not set(tr.run) & set(te.run)
        det = fit_detectors(tr, seed=k)
        te["anom"], te["score"] = det_flags(det, te)
        cls = fit_classifier(tr[~tr.scenario.eq("cpu_burn")], seed=k)
        P = cls.predict_proba(te[CLS_FEATURES].values)
        te["pred"] = [cls.classes_[i] for i in P.argmax(1)]
        te["conf"] = P.max(1)
        oof.append(te)
    oof = pd.concat(oof)

    R.append("## Detector (IsolationForest per service, out-of-fold)\n")
    hh = oof[oof.label == "healthy"]
    R.append(f"- false-alarm rate on healthy windows (incl. traffic surges and good deploys): "
             f"{hh.anom.mean():.4f} per window ({int(hh.anom.sum())} of {len(hh)})")
    R.append("\n| scenario | target windows flagged (rel 8-60 s) | median time to first persistent flag (s) |\n|---|---|---|")
    for sc, g in oof[(oof.scenario != "traffic_surge") & (oof.scenario != "good_deploy")].groupby("scenario"):
        tg = g[(g.service == g.target) & (g.rel >= 8) & (g.rel <= 60)]
        ttd = []
        for _, gr in g[g.service == g.target].groupby("run"):
            gr = gr[gr.rel >= 0].sort_values("end")
            flag = gr.anom.rolling(3).sum().eq(3)
            ttd.append(gr.rel[flag].iloc[0] if flag.any() else np.nan)
        R.append(f"| {sc} | {tg.anom.mean():.2f} | {np.nanmedian(ttd) if not np.all(np.isnan(ttd)) else float('nan'):.0f} |")

    R.append("\n## Fault classifier (calibrated gradient boosting, out-of-fold, target-service windows)\n")
    cl = oof[oof.label.isin(CLASSES) & (oof.scenario != "cpu_burn")]
    cl = cl[(cl.label == "healthy") | ((cl.service == cl.target) & (cl.rel >= 8))]
    # abstain threshold chosen from OOF: smallest tau giving >=95% accuracy on answered windows
    taus = np.arange(0.40, 0.96, 0.05)
    best = 0.5
    for t in taus:
        ans = cl[cl.conf >= t]
        if len(ans) and (ans.pred == ans.label).mean() >= 0.95 and len(ans) / len(cl) >= 0.8:
            best = float(t)
            break
    ans = cl[cl.conf >= best]
    R.append(f"- abstain threshold (chosen out-of-fold): {best:.2f}; coverage {len(ans) / len(cl):.2%}; "
             f"accuracy on answered {(ans.pred == ans.label).mean():.3f}")
    R.append(f"- macro-F1 (forced answer, all windows): {f1_score(cl.label, cl.pred, average='macro'):.3f}; "
             f"macro-F1 on answered windows: {f1_score(ans.label, ans.pred, average='macro'):.3f}")
    labs = [c for c in CLASSES if c in set(cl.label)]
    R.append("\nConfusion matrix (rows true, cols predicted, forced answer):\n\n```\n" +
             pd.DataFrame(confusion_matrix(cl.label, cl.pred, labels=labs), index=labs, columns=labs).to_string() + "\n```")
    R.append("\nPer-class recall:\n\n" + pd.Series({c: float((cl[cl.label == c].pred == c).mean()) for c in labs})
             .round(3).to_frame("recall").to_markdown())

    # ---- final fit on all training runs, then unseen-fault test
    det_final = fit_detectors(df)
    cls_final = fit_classifier(df[df.scenario != "cpu_burn"])
    unseen = df[(df.scenario == "cpu_burn") & (df.service == df.target) & (df.rel >= 8)]
    if len(unseen):
        P = cls_final.predict_proba(unseen[CLS_FEATURES].values)
        conf = P.max(1)
        abst = float((conf < best).mean())
        forced = pd.Series([cls_final.classes_[i] for i in P.argmax(1)]).value_counts().to_dict()
        R.append(f"\n## Unseen fault (cpu_burn, never trained on)\n\n- abstained on {abst:.0%} of {len(unseen)} windows at "
                 f"tau={best:.2f}; the rest were forced into: {forced}")
        R.append("- note: this model was fitted on all training runs, so this is a true unseen-class test, "
                 "but with a single unseen fault type and few runs; treat as indicative only.")

    # ---- RCA ranker, out-of-fold
    fault_rows = df[~df.scenario.isin(HEALTHY_SCEN)]
    ev_rows = []
    for r in fault_rows.run.unique():
        g = fault_rows[fault_rows.run == r]
        tgt = g.target.iloc[0]
        for rel in (10, 14, 20, 30, 40):
            at = g[(g.rel >= rel - 1) & (g.rel <= rel + 1)]
            if at.service.nunique() < len(config.SERVICES):
                continue
            ev_rows.append((r, rel, tgt, at.groupby("service").first()))
    # anomalies per window come from the out-of-fold detector flags
    flagmap = oof.set_index(["run", "service", "end"])[["anom", "score"]]
    recs = []
    for r, rel, tgt, at in ev_rows:
        if r not in set(oof.run):
            continue
        t_end = at.end.max()
        an, sc, onset, feats = {}, {}, {}, {}
        for s in config.SERVICES:
            hist = oof[(oof.run == r) & (oof.service == s) & (oof.end <= t_end)].sort_values("end")
            an[s] = bool(hist.anom.iloc[-1]) if len(hist) else False
            sc[s] = float(hist.score.iloc[-1]) if len(hist) else np.nan
            run_flag = hist.anom.rolling(3).sum().eq(3)
            idx = hist.end[run_flag & (hist.rel >= -5)]
            onset[s] = float(idx.iloc[0]) if len(idx) else None
            feats[s] = at.loc[s].to_dict() if s in at.index else {}
        depf = {(c, k): float(at.loc[c].get(f"depfail_{k}", 0) or 0) for c, ks in config.TOPOLOGY.items() for k in ks
                if c in at.index}
        tab = evidence_table(sc, an, onset, depf, feats)
        tab["run"], tab["rel"], tab["is_root"] = r, rel, [int(s == tgt) for s in tab.index]
        tab["service"] = tab.index
        recs.append((tab, feats, an))
    ranking = pd.concat([t for t, _, _ in recs]).reset_index(drop=True)
    R.append("\n## Root-cause ranking (out-of-fold; incidents at several detection delays)\n")
    rr = []
    for tr_runs, te_runs in folds(df):
        trr, ter = ranking[ranking.run.isin(tr_runs)], ranking[ranking.run.isin(te_runs)]
        if ter.empty or trr.empty:
            continue
        m = HistGradientBoostingClassifier(max_depth=3, max_iter=80, learning_rate=0.08, min_samples_leaf=10,
                                           l2_regularization=1.0, random_state=0).fit(trr[EVIDENCE].values, trr.is_root)
        for (run, rel), g in ter.groupby(["run", "rel"]):
            p = m.predict_proba(g[EVIDENCE].values)[:, 1]
            order = list(g.service.values[np.argsort(-p)])
            tgt = g.service[g.is_root == 1].iloc[0]
            idx_rec = next(i for i, (t, _, _) in enumerate(recs) if t.run.iloc[0] == run and t.rel.iloc[0] == rel)
            _, feats, an = recs[idx_rec]
            rr.append({"run": run, "rel": rel, "learned": order, "tgt": tgt,
                       "rule": deepest_anomalous(an) or list(config.SERVICES),
                       "baro": baro_rank(feats, base), "random": list(np.random.default_rng(hash((run, rel)) % 2**32).permutation(config.SERVICES))})
    R.append("| method | top-1 | top-3 | incidents |\n|---|---|---|---|")
    for name in ("learned", "rule", "baro", "random"):
        t1 = np.mean([x[name][:1] == [x["tgt"]] for x in rr])
        t3 = np.mean([x["tgt"] in x[name][:3] for x in rr])
        R.append(f"| {'learned ranker' if name == 'learned' else {'rule': 'deepest anomalous (old prototype rule)', 'baro': 'BARO-style robust z', 'random': 'random'}[name]} | {t1:.3f} | {t3:.3f} | {len(rr)} |")

    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text("\n".join(R) + "\n", encoding="utf-8")
    print("\n".join(R))

    if not a.no_save:
        ranker_model = HistGradientBoostingClassifier(max_depth=3, max_iter=80, learning_rate=0.08, min_samples_leaf=10,
                                                      l2_regularization=1.0, random_state=0).fit(ranking[EVIDENCE].values, ranking.is_root)
        desc = f"{len(runs)} no-action live runs, training seeds 1000+, scenarios {sorted(set(df.scenario))}"
        artifacts.save("baselines", base, training_data=desc, features=["req_rate", "p95_s", "cpu_cores", "mem_bytes",
                                                                       "error_ratio", "cpu_per_req"])
        artifacts.save("detectors", det_final, training_data=desc, features=DET_FEATURES)
        artifacts.save("classifier", FaultClassifier(cls_final, CLS_FEATURES, list(cls_final.classes_), best),
                       training_data=desc, features=CLS_FEATURES, extra={"abstain_below": best})
        artifacts.save("ranker", Ranker(ranker_model), training_data=desc, features=EVIDENCE)
        print(f"\nartifacts saved to {artifacts.ARTIFACT_DIR}")


if __name__ == "__main__":
    main()
