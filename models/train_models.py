"""Train detector, classifier and root-cause ranker from live evaluator runs; evaluate without leakage.

    python models/train_models.py [--runs data/runs] [--out docs/results/models_cv.md] [--no-save]

* The split unit is the whole run (grouped, stratified by scenario). No window of a run is ever in both
  train and test; calibration and thresholds are fitted on training data only.
* The abstain threshold is chosen by an INNER cross-validation inside each training fold (nested), then
  applied to the untouched outer test fold. The threshold of the frozen model comes from out-of-fold
  predictions over all training runs.
* cpu_burn is the UNSEEN fault: excluded from every training step, used only to test abstention.
  A second unseen-fault test holds out each supported fault type in turn (leave-one-fault-type-out).
* Runs listed in data/runs/EXCLUDED.json (written by models/check_runs.py) are skipped.
* Every number printed here is what ends up in docs/results/models_cv.md.
"""
import argparse
import json
import sys
import warnings
import zlib
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import confusion_matrix, f1_score
from sklearn.model_selection import StratifiedGroupKFold

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import envinfo  # noqa: E402
from eternalai import artifacts, config  # noqa: E402
from eternalai.calibrate import TemperatureCalibrated  # noqa: E402
from eternalai.classify import ABSTAIN, CLASSES, FaultClassifier  # noqa: E402
from eternalai.detect import FEATURES as DET_FEATURES, IF_SLACK, LIMIT_MARGIN, TWO_SIDED, fit_service  # noqa: E402
from eternalai.features.window import FEATURE_NAMES, fit_baseline, window_features  # noqa: E402
from eternalai.novelty import NOVELTY_FEATURES, NoveltyGate  # noqa: E402
from eternalai.rca import EVIDENCE, Ranker, baro_rank, deepest_anomalous, evidence_table  # noqa: E402
from eternalai.safe_model import SafeHGB  # noqa: E402

warnings.filterwarnings("ignore")
HEALTHY_SCEN = {"traffic_surge", "good_deploy"}
# v2 (Amendment 4, E2): absolute memory levels depend on container age and prior load; the classifier gets memory growth relative to the service's own past
# (`mem_rel_growth`) and the memory slope instead.
ABSOLUTE_MEM = {"mem_ratio", "mem_z", "mem_share", "mem_ratio_obs", "mem_z_obs", "mem_share_obs"}
CLS_FEATURES = [f for f in FEATURE_NAMES if f not in ABSOLUTE_MEM]
MEM_FEATURES = {"mem_ratio", "mem_z", "mem_ratio_obs", "mem_z_obs"}   # ablation: baseline of `orders` memory drifts
TAUS = np.round(np.arange(0.40, 0.96, 0.05), 2)
SEEDS = "fold split seeds 0 (main CV) and 1 (nested threshold CV); model seeds 0..4 by fold index; run seeds 1000-1707 (v1) and 1800-1842 (v2 fresh)"


# ------------------------------------------------------------------ data
def load_runs(path):
    excl = Path(path) / "EXCLUDED.json"
    excluded = json.loads(excl.read_text()) if excl.exists() else {}
    runs = []
    for js in sorted(Path(path).glob("*.json")):
        if js.name == "EXCLUDED.json" or js.stem in excluded:
            continue
        truth = json.loads(js.read_text())
        raw = pd.read_csv(js.with_suffix(".csv"), index_col=[0, 1])
        frames = {s: raw.loc[s].dropna(axis=1, how="all") if s in raw.index.get_level_values(0) else None
                  for s in config.SERVICES}
        runs.append({"id": js.stem, "truth": truth, "frames": {k: v for k, v in frames.items() if v is not None}})
    return runs, excluded


# The evaluator waits 45 s after restoring the stack, but the restore tail (callers erroring) lasts until ~40 s before
# injection; pooled over all runs the error ratio is 0.148 / 0.040 / 0.003 / 0.000 in the 5 s bins starting at
# -50 / -45 / -40 / -35 s (scripts/debug_settle.py). Everything earlier than -40 s is therefore not "healthy".
SETTLE_S = 40.0


def make_baselines(runs):
    """Healthy-only per-service baseline from the CLEAN pre-injection period [t0-45 s, t0-5 s] of all runs.
    The saved data starts earlier, but its first part is the restore of the previous run (containers coming back up,
    callers erroring): attempt 1-3 fitted baselines and labelled 'healthy' windows on that, which contaminated them."""
    out = {}
    for s in config.SERVICES:
        pre = []
        for r in runs:
            if s in r["frames"]:
                f, t0 = r["frames"][s], r["truth"]["t_inject"]
                pre.append(f[(f.index >= t0 - SETTLE_S) & (f.index < t0 - 5)])
        out[s] = fit_baseline(pd.concat(pre))
    return out


def build_rows(runs, baselines, window_s=10.0):
    """One row per (run, service, 2 s step). A fault label is given only when the whole feature window lies after the
    injection (rel >= window_s); windows that straddle the onset are labelled 'other' and are used neither to train nor
    to evaluate the classifier (attempt 1 labelled them as faults and the model could not tell them from healthy)."""
    rows = []
    for r in runs:
        t0, tr = r["truth"]["t_inject"], r["truth"]
        for s, df in r["frames"].items():
            grid = np.arange(t0 - 110, min(t0 + 70, df.index.max()), 2.0)
            for end in grid:
                w = df[(df.index <= end) & (df.index > end - 150)]
                if len(w) < 20:
                    continue
                f = window_features(w, baselines[s], window_s)
                for k in ("depfail_inventory", "depfail_payments", "depfail_orders"):
                    f[k] = float(w[k].tail(5).mean()) if k in w else np.nan
                rel = end - t0
                # a window is CLEAN-healthy only if it lies wholly inside [t0-SETTLE_S, t0-5]: earlier data overlaps the
                # restore of the previous run
                clean_pre = -(SETTLE_S - window_s) <= rel <= -5
                if tr["scenario"] in HEALTHY_SCEN:
                    label = "healthy" if clean_pre or rel >= max(window_s, 20 if tr["scenario"] == "good_deploy" else 0) \
                        else "other"
                elif clean_pre:
                    label = "healthy"
                elif rel >= window_s and s == tr["target"]:
                    label = tr["expected_label"]
                else:
                    label = "other"
                rows.append({"run": r["id"], "scenario": tr["scenario"], "target": tr["target"], "service": s,
                             "rel": rel, "end": end, "label": label, "window_s": window_s, **f})
    return pd.DataFrame(rows)


def folds(d, n=5, seed=0):
    runs = d.drop_duplicates("run")[["run", "scenario"]].reset_index(drop=True)
    for tri, tei in StratifiedGroupKFold(n_splits=n, shuffle=True, random_state=seed).split(runs, runs.scenario, runs.run):
        yield set(runs.run[tri]), set(runs.run[tei])


def known_mask(d):
    """Windows used to judge the classifier on KNOWN classes (healthy, or the target service after onset)."""
    return d.label.isin(CLASSES) & (d.scenario != "cpu_burn") & (
        (d.label == "healthy") | ((d.service == d.target) & (d.rel >= d.window_s)))


def train_mask(d):
    return d.label.isin(CLASSES) & (d.scenario != "cpu_burn")


# ------------------------------------------------------------------ detector
def fit_detectors(df, seed=0, margin=None, if_mode=None):
    """One IsolationForest per service on healthy rows; threshold from a held-out slice of healthy RUNS."""
    h = df[df.label == "healthy"]
    runs = sorted(h.run.unique())
    val_runs = set(np.random.default_rng(seed).choice(runs, max(2, len(runs) // 5), replace=False))
    det = {}
    for s in config.SERVICES:
        hs = h[h.service == s]
        tr, va = hs[~hs.run.isin(val_runs)], hs[hs.run.isin(val_runs)]
        kw = {} if margin is None else {"limit_margin": margin}
        if if_mode is not None:
            kw["if_mode"] = if_mode
        det[s] = fit_service(tr[DET_FEATURES].values, va[DET_FEATURES].values, seed=seed, **kw)
    return det


def fp_events(oof):
    """Persistent-flag false alarms (3 consecutive 2 s flags) on clean pre-injection healthy windows:
    (events, service-minutes, events by service). This, not the per-window rate, is what opens incidents."""
    ev_total, minutes, by_svc = 0, 0.0, {}
    for (_, svc_), g in oof[oof.rel < 0].groupby(["run", "service"]):
        g = g[g.label == "healthy"].sort_values("end")
        if len(g) < 3:
            continue
        persistent = g.anom.rolling(3).sum().eq(3)
        starts = int((persistent & ~persistent.shift(1, fill_value=False)).sum())
        ev_total += starts
        by_svc[svc_] = by_svc.get(svc_, 0) + starts
        minutes += len(g) * 2.0 / 60.0
    return ev_total, minutes, by_svc


def detector_sweep(df, margins, out, run_dir, excluded):
    """Choose the limit margin by CV: detection of fault windows versus persistent false alarms (no held-out data)."""
    configs = [("margin 0.25, forest at validation 99.8% quantile", 0.25, "quantile"),
               ("margin 1, forest at validation 99.8% quantile", 1.0, "quantile"),
               ("margin 1, forest threshold = max validation score + 0.02", 1.0, 0.02),
               ("margin 1, forest threshold = max validation score + 0.05", 1.0, 0.05),
               ("margin 1, forest off (limits only)", 1.0, "off"),
               ("margin 2, forest off (limits only)", 2.0, "off")]
    rows = []
    for label, m, mode in configs:
        parts = []
        for k, (tr_runs, te_runs) in enumerate(folds(df, 5, 0)):
            tr, te = df[df.run.isin(tr_runs)], df[df.run.isin(te_runs)].copy()
            te["anom"], te["score"] = det_flags(fit_detectors(tr, seed=k, margin=m, if_mode=mode), te)
            parts.append(te)
        o = pd.concat(parts)
        tg = o[(o.service == o.target) & (o.rel >= o.window_s) & (o.rel <= 60) & ~o.scenario.isin(HEALTHY_SCEN)]
        ev, mins, _ = fp_events(o)
        per_scen = tg.groupby("scenario").anom.mean()
        rows.append({"configuration": label, "fault_window_flag_rate": float(tg.anom.mean()),
                     "min_scenario_flag_rate": float(per_scen.min()), "worst_scenario": per_scen.idxmin(),
                     "healthy_window_flag_rate": float(o[o.label == "healthy"].anom.mean()),
                     "persistent_false_alarms_per_100_service_min": 100 * ev / max(mins, 1e-9),
                     "_margin": m, "_if_mode": str(mode)})
    t = pd.DataFrame(rows)
    R = ["# Detector configuration sweep (grouped CV by run)\n",
         "Generated by `python models/train_models.py --detector-sweep`. Margin = how far beyond the observed healthy range a "
         "feature may go (in healthy spreads) before its learned limit flags it. Selection rule, fixed before this run: among "
         "configurations in which every fault scenario keeps a flag rate >= 0.95, take the lowest persistent false-alarm rate; "
         "the aim is <= 1 per 100 service-minutes, and the report says plainly whether any configuration reaches it.\n",
         *envinfo.env_lines(SEEDS, run_dir, excluded), "",
         t.drop(columns=["_margin", "_if_mode"]).round(3).to_markdown(index=False)]
    ok = t[t.min_scenario_flag_rate >= 0.95]
    if len(ok):
        best = ok.loc[ok.persistent_false_alarms_per_100_service_min.idxmin()]
        R.append(f"\nChosen: **{best.configuration}** (margin {best._margin}, forest mode {best._if_mode}); "
                 f"persistent false alarms {best.persistent_false_alarms_per_100_service_min:.2f} per 100 service-minutes; "
                 f"target <= 1 {'met' if best.persistent_false_alarms_per_100_service_min <= 1.0 else 'NOT met'}.")
    else:
        R.append("\nNo configuration kept every scenario at a flag rate of 0.95.")
    Path(out).write_text("\n".join(R) + "\n", encoding="utf-8")
    print("\n".join(R))


def det_flags(det, df):
    out, sc = np.zeros(len(df), dtype=bool), np.full(len(df), np.nan)
    for s, d in det.items():
        m = (df.service == s).values
        sc[m] = -d.model.score_samples(df.loc[m, DET_FEATURES].values)
        flag = sc[m] > d.threshold
        for f, (lo, hi) in d.limits.items():          # learned healthy-range limits (NaN never flags)
            v = df.loc[m, f].values.astype(float)
            with np.errstate(invalid="ignore"):
                flag |= (v > hi) | ((v < lo) if f in TWO_SIDED else False)
        out[m] = flag
    out |= (df.up_frac == 0).values | df.up_frac.isna().values   # not scraped = anomalous (missing is not normal)
    return out, sc


# ------------------------------------------------------------------ classifier
def fit_classifier(df, seed=0, features=None, calibrate=True):
    features = features or CLS_FEATURES
    d = df[train_mask(df)]
    X, y, g = d[features].values, d.label.values, d.run.values
    base = SafeHGB(max_depth=4, max_iter=150, learning_rate=0.06, min_samples_leaf=15, l2_regularization=1.0,
                   class_weight="balanced", random_state=seed)
    if not calibrate:
        return base.fit(X, y)
    inner = list(StratifiedGroupKFold(3, shuffle=True, random_state=seed).split(X, y, g))  # grouped by run
    # temperature scaling (one parameter, arg-max unchanged). Attempt 1-2 used per-class sigmoid calibration, which
    # collapsed rare-class predictions into "healthy"; see eternalai/calibrate.py and docs/DATA.md.
    return TemperatureCalibrated(base, inner).fit(X, y)


def predict(cls, d, features=None):
    P = cls.predict_proba(d[features or CLS_FEATURES].values)
    return np.array([cls.classes_[i] for i in P.argmax(1)]), P.max(1), P


def fit_gate(df, seed=0):
    """Novelty gate on the known-class training windows; threshold from out-of-fold distances grouped by run."""
    d = df[train_mask(df)]
    X = d[NOVELTY_FEATURES].to_numpy(dtype=float)
    folds_ = list(StratifiedGroupKFold(5, shuffle=True, random_state=seed).split(X, d.label.values, d.run.values))
    return NoveltyGate().fit(X, folds_)


def gate_distance(gate, d):
    return gate.distance(d[gate.features].to_numpy(dtype=float))


def oof_known(df, n=3, seed=0, features=None, calibrate=True):
    """Out-of-fold predictions for the known-class windows of `df` (all inside df's own runs)."""
    parts = []
    for k, (tr_runs, te_runs) in enumerate(folds(df, n, seed)):
        tr, te = df[df.run.isin(tr_runs)], df[df.run.isin(te_runs)]
        te = te[known_mask(te)].copy()
        cls = fit_classifier(tr, seed + k, features, calibrate)
        te["pred"], te["conf"], _ = predict(cls, te, features)
        parts.append(te)
    return pd.concat(parts)


def choose_tau(oof):
    """Smallest threshold giving >= 95% accuracy on answered windows with >= 80% coverage (else 0.5, flagged)."""
    for t in TAUS:
        ans = oof[oof.conf >= t]
        if len(ans) and (ans.pred == ans.label).mean() >= 0.95 and len(ans) / len(oof) >= 0.8:
            return float(t), True
    return 0.5, False


def ece_and_table(conf, correct, bins=10):
    edges = np.linspace(0, 1, bins + 1)
    rows, ece = [], 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (conf > lo) & (conf <= hi) if lo > 0 else (conf >= lo) & (conf <= hi)
        if m.sum():
            gap = abs(correct[m].mean() - conf[m].mean())
            ece += m.sum() / len(conf) * gap
            rows.append((f"{lo:.1f}-{hi:.1f}", int(m.sum()), float(conf[m].mean()), float(correct[m].mean())))
    return float(ece), rows


def det_final_for_report(df):
    """Detectors fitted on all runs, used only to describe which limits the (out-of-fold) false alarms exceeded."""
    return fit_detectors(df)


def cv_oof(df, extras=True):
    """Out-of-fold detector flags and classifier predictions (grouped by run). `extras` adds the uncalibrated
    classifier and the memory-feature ablation."""
    no_mem = [f for f in CLS_FEATURES if f not in MEM_FEATURES]
    oof = []
    for k, (tr_runs, te_runs) in enumerate(folds(df, 5, 0)):
        tr, te = df[df.run.isin(tr_runs)], df[df.run.isin(te_runs)].copy()
        assert not set(tr.run) & set(te.run)
        det = fit_detectors(tr, seed=k)
        te["anom"], te["score"] = det_flags(det, te)
        cls = fit_classifier(tr, k)
        te["pred"], te["conf"], _ = predict(cls, te)
        gate = fit_gate(tr, k)                       # fitted on the training runs only
        te["nov"], te["nov_thr"] = gate_distance(gate, te), gate.threshold_
        if extras:
            raw = fit_classifier(tr, k, calibrate=False)
            te["pred_raw"], te["conf_raw"], _ = predict(raw, te)
            abl = fit_classifier(tr, k, no_mem)
            te["pred_nomem"], te["conf_nomem"], _ = predict(abl, te, no_mem)
        oof.append(te)
    return pd.concat(oof)


def sweep(runs, base, windows, out, run_dir, excluded):
    """Pick the feature-window length by cross-validation: a small, explicit search (3 candidates)."""
    rows = []
    for w in windows:
        d = build_rows(runs, base, float(w))
        o = cv_oof(d, extras=False)
        kn = o[known_mask(o)]
        faults = [c for c in CLASSES if c != "healthy" and c in set(kn.label)]
        rec = {c: float((kn[kn.label == c].pred == c).mean()) for c in faults}
        tg = o[(o.service == o.target) & (o.rel >= o.window_s) & (o.rel <= 60) & ~o.scenario.isin(HEALTHY_SCEN)
               & (o.scenario != "cpu_burn")]
        hh = o[o.label == "healthy"]
        rows.append({"window_s": w, "macro_F1": f1_score(kn.label, kn.pred, average="macro"),
                     "mean_fault_recall": float(np.mean(list(rec.values()))), **{f"recall_{c}": v for c, v in rec.items()},
                     "detector_flag_rate_on_fault_windows": float(tg.anom.mean()),
                     "detector_false_alarm_rate": float(hh.anom.mean())})
    t = pd.DataFrame(rows)
    best = t.loc[t.macro_F1.idxmax(), "window_s"]
    R = ["# Feature-window sweep (grouped CV by run)\n",
         "Generated by `python models/train_models.py --sweep 10 20 30`. The window length was chosen by out-of-fold macro-F1 "
         "of the known-class classifier. Longer windows blur the onset of a fault (see `scripts/debug_windows.py`), but the "
         "evaluated windows differ per row because a fault window must lie fully after injection, so compare with that in mind.\n",
         *envinfo.env_lines(SEEDS, run_dir, excluded), "", t.round(3).to_markdown(index=False),
         f"\nChosen by the rule above: **{best:.0f} s**. A live-system consideration points the same way: the engine "
         f"diagnoses about 10 s after onset, so a window much longer than that would mix pre-fault data into every diagnosis."]
    Path(out).write_text("\n".join(R) + "\n", encoding="utf-8")
    print("\n".join(R))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", default="data/runs")
    ap.add_argument("--out", default="docs/results/models_cv.md")
    ap.add_argument("--window", type=float, default=10.0, help="feature window in seconds")
    ap.add_argument("--sweep", type=int, nargs="*", help="compare these window lengths and exit")
    ap.add_argument("--detector-sweep", action="store_true", help="compare detector configurations and exit")
    ap.add_argument("--no-save", action="store_true")
    a = ap.parse_args()
    runs, excluded = load_runs(a.runs)
    if len(runs) < 20:
        sys.exit(f"only {len(runs)} runs found; collect more with models/collect_runs.py")
    base = make_baselines(runs)
    if a.sweep:
        return sweep(runs, base, a.sweep, "docs/results/window_sweep.md", a.runs, excluded)
    df = build_rows(runs, base, a.window)
    if a.detector_sweep:
        return detector_sweep(df, None, "docs/results/detector_margin.md", a.runs, excluded)
    no_mem = [f for f in CLS_FEATURES if f not in MEM_FEATURES]
    R = ["# Model evaluation on live-stack runs (grouped CV by run)\n",
         "Generated by `models/train_models.py`. These are cross-validation numbers on TRAINING-seed, no-action runs. "
         "Held-out results from the evaluator with unseen seeds are in EVALUATION.md.\n",
         f"- runs used: {len(runs)} (excluded as corrupted: {len(excluded)}); per scenario: "
         f"{pd.Series([r['truth']['scenario'] for r in runs]).value_counts().to_dict()}",
         f"- window rows: {len(df)}; label counts: {df.label.value_counts().to_dict()}",
         *envinfo.env_lines(SEEDS, a.runs, excluded)]

    # ================= main grouped CV: detector, calibrated classifier, raw classifier, memory ablation
    oof = cv_oof(df)
    kn = oof[known_mask(oof)]

    R.append("\n## Detector (IsolationForest per service, out-of-fold)\n")
    hh = oof[oof.label == "healthy"]
    R.append(f"- false-alarm rate on healthy windows (incl. traffic surges and good deploys): "
             f"{hh.anom.mean():.4f} per window ({int(hh.anom.sum())} of {len(hh)})")
    # Event level: what the engine acts on is a PERSISTENT flag (3 consecutive 2 s ticks), and 10 s windows overlap, so
    # the per-window rate overstates the protection that persistence gives. Count persistent-flag events directly.
    ev_total, minutes, ev_by_svc = fp_events(oof)
    R.append(f"- persistent-flag false alarms (the events the engine would open an incident for), pre-injection healthy "
             f"windows: {ev_total} events in {minutes:.0f} healthy service-minutes = **{100 * ev_total / max(minutes, 1e-9):.1f} per "
             f"100 service-minutes**; by service: {ev_by_svc}")
    upper = 100 * 3.0 / max(minutes, 1e-9) if ev_total == 0 else float("nan")
    if ev_total == 0:
        R.append(f"- zero events is an observation, not proof of zero: by the rule of three the 95% upper bound on the rate is "
                 f"about {upper:.1f} per 100 service-minutes given only {minutes:.0f} healthy service-minutes")
    R.append(f"- detector configuration in use: learned-limit margin {LIMIT_MARGIN}, forest threshold = largest healthy "
             f"validation score + {IF_SLACK} (chosen by `--detector-sweep`, docs/results/detector_margin.md; the forest "
             f"turned out to add nothing measurable over the limits)")
    R.append("\n| scenario | target windows flagged (rel 8-60 s) | median time to first persistent flag (s) |\n|---|---|---|")
    for sc, g in oof[~oof.scenario.isin(HEALTHY_SCEN)].groupby("scenario"):
        tg = g[(g.service == g.target) & (g.rel >= g.window_s) & (g.rel <= 60)]
        ttd = []
        for _, gr in g[g.service == g.target].groupby("run"):
            gr = gr[gr.rel >= 0].sort_values("end")
            flag = gr.anom.rolling(3).sum().eq(3)
            ttd.append(gr.rel[flag].iloc[0] if flag.any() else np.nan)
        R.append(f"| {sc} | {tg.anom.mean():.2f} | "
                 f"{np.nanmedian(ttd) if not np.all(np.isnan(ttd)) else float('nan'):.0f} |")

    R.append("\n## Fault classifier (calibrated gradient boosting, out-of-fold, known classes)\n")
    labs = [c for c in CLASSES if c in set(kn.label)]
    R.append(f"- macro-F1, forced answer: **{f1_score(kn.label, kn.pred, average='macro'):.3f}** "
             f"({len(kn)} windows from {kn.run.nunique()} runs)")
    R.append("\nConfusion matrix (rows true, columns predicted):\n\n```\n" +
             pd.DataFrame(confusion_matrix(kn.label, kn.pred, labels=labs), index=labs, columns=labs).to_string() + "\n```")
    R.append("\nPer-class recall:\n\n" + pd.Series({c: float((kn[kn.label == c].pred == c).mean()) for c in labs})
             .round(3).to_frame("recall").to_markdown())

    # ---- calibration
    ece_cal, tab = ece_and_table(kn.conf.values, (kn.pred == kn.label).values.astype(float))
    ece_raw, _ = ece_and_table(kn.conf_raw.values, (kn.pred_raw == kn.label).values.astype(float))
    R.append(f"\n### Calibration of the top-class probability (out-of-fold)\n\n"
             f"- expected calibration error: **{ece_cal:.3f}** calibrated (temperature scaling, fitted inside training folds) versus "
             f"{ece_raw:.3f} for the same model uncalibrated (ECE = weighted gap between confidence and accuracy; 0 is perfect)")
    R.append("\n| confidence bin | windows | mean confidence | accuracy |\n|---|---|---|---|\n" +
             "\n".join(f"| {b} | {n} | {c:.3f} | {acc:.3f} |" for b, n, c, acc in tab))
    # The overall ECE is dominated by the many easy 'healthy' windows (attempt 1 passed it at 0.026 while fault
    # predictions were badly off), so the probability a user actually sees, the one attached to a FAULT prediction,
    # is checked on its own.
    fp = kn[kn.pred != "healthy"]
    if len(fp):
        ece_fault, tab_f = ece_and_table(fp.conf.values, (fp.pred == fp.label).values.astype(float), bins=5)
    else:
        ece_fault, tab_f = float("nan"), []
    R.append(f"\n- calibration on windows predicted as a FAULT class only ({len(fp)} windows): ECE **{ece_fault:.3f}**")
    if tab_f:
        R.append("\n| confidence bin | windows | mean confidence | accuracy |\n|---|---|---|---|\n" +
                 "\n".join(f"| {b} | {n} | {c:.3f} | {acc:.3f} |" for b, n, c, acc in tab_f))
    ece_ok = bool(ece_cal <= 0.05 and len(fp) >= 50 and ece_fault <= 0.10)
    R.append(f"\n- decision: the dashboard {'shows' if ece_ok else 'does NOT show'} the probability as a percentage "
             f"(rule, fixed before the attempt-2 results were seen: overall ECE <= 0.05 AND ECE on fault predictions <= 0.10 "
             f"with at least 50 such windows). "
             f"{'' if ece_ok else 'It shows the predicted class with a calibration-not-verified note instead.'}")

    # ---- memory-baseline drift ablation
    f_full = f1_score(kn.label, kn.pred, average="macro")
    f_nomem = f1_score(kn.label, kn.pred_nomem, average="macro")
    R.append(f"\n### Ablation for the `orders` memory-baseline drift found in the data check\n\n"
             f"- macro-F1 with all features {f_full:.3f}; without the baseline-relative memory features "
             f"(`mem_ratio`, `mem_z` and their masks) {f_nomem:.3f}; difference {f_full - f_nomem:+.3f}. "
             f"`mem_share` and the memory slope, which do not depend on a baseline, stay in both.")

    # ---- abstain threshold: final (from OOF) and nested (chosen inside training folds)
    tau, tau_ok = choose_tau(kn)
    R.append(f"\n### Abstain threshold\n\n- frozen-model threshold (from out-of-fold predictions over all training runs): "
             f"**{tau:.2f}**{'' if tau_ok else ' (fallback: no threshold met the 95% accuracy / 80% coverage target)'}")
    nested = []
    for k, (tr_runs, te_runs) in enumerate(folds(df, 5, 1)):
        tr, te = df[df.run.isin(tr_runs)], df[df.run.isin(te_runs)]
        tau_k, ok_k = choose_tau(oof_known(tr, 3, k))          # threshold chosen on training runs only
        cls = fit_classifier(tr, k)
        gate_k = fit_gate(tr, k)
        tk = te[known_mask(te)].copy()
        tk["pred"], tk["conf"], _ = predict(cls, tk)
        tk["novel"] = gate_distance(gate_k, tk) > gate_k.threshold_
        ans = tk[(tk.conf >= tau_k) & ~tk.novel]            # abstain if low confidence OR far from every known window
        nested.append((tau_k, ok_k, len(ans) / len(tk), float((ans.pred == ans.label).mean()), len(tk),
                       float(tk.novel.mean())))
    ne = pd.DataFrame(nested, columns=["tau", "target_met", "coverage", "answered_accuracy", "windows", "gate_abstained"])
    R.append("- nested check (threshold chosen by inner CV on each training fold, applied to the untouched test fold):\n\n" +
             ne.round(3).to_markdown())
    R.append(f"\n  mean test-fold coverage {ne.coverage.mean():.3f}, mean answered accuracy {ne.answered_accuracy.mean():.3f} "
             f"(target was 0.95 at coverage >= 0.8)")

    # ================= unseen faults
    R.append("\n## Unseen-fault behaviour\n")
    cls_final = fit_classifier(df)
    gate_final = fit_gate(df)
    # cpu_burn: never in any training set; its windows sit in the test folds of the main CV, so these are out-of-fold
    un = oof[(oof.scenario == "cpu_burn") & (oof.service == oof.target) & (oof.rel >= oof.window_s)].copy()
    if len(un):
        un["novel"] = un.nov > un.nov_thr
        un["low_conf"] = un.conf < tau
        un["abstain"] = un.novel | un.low_conf
        R.append(f"- **cpu_burn (never in any training set; out-of-fold)**: abstained on **{un.abstain.mean():.0%}** of {len(un)} "
                 f"windows (novelty gate {un.novel.mean():.0%}; confidence below {tau:.2f}: {un.low_conf.mean():.0%}). "
                 f"For comparison the confidence rule alone abstains on {un.low_conf.mean():.0%}. When it did answer it said: "
                 f"{un[~un.abstain].pred.value_counts().to_dict() or 'nothing'}")
    kn_abst = (kn.nov > kn.nov_thr) | (kn.conf < tau)
    R.append(f"- false abstention on KNOWN-class windows (out-of-fold): {kn_abst.mean():.1%} "
             f"(gate alone {(kn.nov > kn.nov_thr).mean():.1%}); nested estimate with thresholds chosen inside training folds: "
             f"{1 - ne.coverage.mean():.1%}")
    R.append("\nLeave-one-fault-type-out: each supported fault type is removed from training entirely (all of its runs), "
             "the confidence threshold and the novelty-gate threshold are both chosen on the remaining runs only, and the "
             "held-out type is then shown to the model.\n")
    lo_rows = []
    for f in ("crash", "latency", "error_spike", "memory_leak", "disk_fill", "bad_deploy"):
        tr = df[df.scenario != f]
        tau_f, _ = choose_tau(oof_known(tr, 3, 0))
        cls_f, gate_f = fit_classifier(tr), fit_gate(tr)
        te = df[(df.scenario == f) & (df.service == df.target) & (df.rel >= df.window_s) & df.label.isin(CLASSES)].copy()
        te["pred"], te["conf"], _ = predict(cls_f, te)
        te["novel"] = gate_distance(gate_f, te) > gate_f.threshold_
        te["abstain"] = te.novel | (te.conf < tau_f)
        lo_rows.append({"held-out type": f, "windows": len(te), "abstained (gate or confidence)": f"{te.abstain.mean():.0%}",
                        "by novelty gate": f"{te.novel.mean():.0%}", "by confidence alone": f"{(te.conf < tau_f).mean():.0%}",
                        "answered (so wrong)": f"{(~te.abstain).mean():.0%}",
                        "what it said when it answered": str(te[~te.abstain].pred.value_counts().to_dict())})
    R.append(pd.DataFrame(lo_rows).to_markdown(index=False))
    R.append("\n- Reading: a held-out type that is answered is answered WRONGLY by construction (the model has no label for it), "
             "so 'answered' is the share of unseen-type windows where the system would have guessed. A model that never "
             "abstains would show 0%. Some held-out types resemble a known one (a bad deploy looks like an error spike), "
             "which no feature-space distance can fully separate.")

    # ================= RCA ranker, out-of-fold
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
    recs = []
    runs_in_oof = set(oof.run)
    for r, rel, tgt, at in ev_rows:
        if r not in runs_in_oof:
            continue
        t_end = at.end.max()
        an, sc, onset, feats = {}, {}, {}, {}
        for s in config.SERVICES:
            hist = oof[(oof.run == r) & (oof.service == s) & (oof.end <= t_end)].sort_values("end")
            an[s] = bool(hist.anom.iloc[-1]) if len(hist) else False
            sc[s] = float(hist.score.iloc[-1]) if len(hist) else np.nan
            idx = hist.end[hist.anom.rolling(3).sum().eq(3) & (hist.rel >= -5)]
            onset[s] = float(idx.iloc[0]) if len(idx) else None
            feats[s] = at.loc[s].to_dict() if s in at.index else {}
        depf = {(c, k): float(at.loc[c].get(f"depfail_{k}", 0) or 0) for c, ks in config.TOPOLOGY.items() for k in ks
                if c in at.index}
        tab_ = evidence_table(sc, an, onset, depf, feats)
        tab_["run"], tab_["rel"], tab_["is_root"] = r, rel, [int(s == tgt) for s in tab_.index]
        tab_["service"] = tab_.index
        recs.append((tab_, feats, an))
    ranking = pd.concat([t for t, _, _ in recs]).reset_index(drop=True)
    key_to_rec = {(t.run.iloc[0], t.rel.iloc[0]): (feats, an) for t, feats, an in recs}
    R.append("\n## Root-cause ranking (out-of-fold; incidents at several detection delays)\n")
    rr = []
    for tr_runs, te_runs in folds(df, 5, 0):
        trr, ter = ranking[ranking.run.isin(tr_runs)], ranking[ranking.run.isin(te_runs)]
        if ter.empty or trr.empty:
            continue
        m = SafeHGB(max_depth=3, max_iter=80, learning_rate=0.08, min_samples_leaf=10, l2_regularization=1.0,
                    random_state=0).fit(trr[EVIDENCE].values, trr.is_root)
        for (run, rel), g in ter.groupby(["run", "rel"]):
            p = m.predict_proba(g[EVIDENCE].values)[:, 1]
            feats, an = key_to_rec[(run, rel)]
            rr.append({"run": run, "rel": rel, "learned": list(g.service.values[np.argsort(-p)]),
                       "tgt": g.service[g.is_root == 1].iloc[0], "rule": deepest_anomalous(an) or list(config.SERVICES),
                       "baro": baro_rank(feats, base),
                       "random": list(np.random.default_rng(zlib.crc32(f"{run}{rel}".encode())).permutation(config.SERVICES))})
    names = {"learned": "learned ranker", "rule": "deepest anomalous (old prototype rule)",
             "baro": "BARO-style robust z (re-implemented, not RCAEval's package)", "random": "random"}
    R.append("| method | top-1 | top-3 | incidents |\n|---|---|---|---|")
    for k, label in names.items():
        t1 = np.mean([x[k][:1] == [x["tgt"]] for x in rr])
        t3 = np.mean([x["tgt"] in x[k][:3] for x in rr])
        R.append(f"| {label} | {t1:.3f} | {t3:.3f} | {len(rr)} |")

    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text("\n".join(R) + "\n", encoding="utf-8")
    print("\n".join(R))

    if not a.no_save:
        ranker_model = SafeHGB(max_depth=3, max_iter=80, learning_rate=0.08, min_samples_leaf=10, l2_regularization=1.0,
                               random_state=0).fit(ranking[EVIDENCE].values, ranking.is_root)
        det_final = fit_detectors(df)
        desc = (f"{len(runs)} no-action live runs (training seeds 1000-1707 and 1800-1842, {len(excluded)} corrupted runs excluded), "
                f"scenarios {sorted(set(df.scenario))}")
        meta = {"data_hash": envinfo.data_hash(a.runs, excluded), "n_runs": len(runs), "excluded_runs": sorted(excluded),
                "abstain_below": tau, "ece_oof": round(ece_cal, 4), "ece_fault_predictions": round(float(ece_fault), 4),
                "show_probability_in_ui": bool(ece_ok), "window_s": a.window,
                "seeds": SEEDS}
        artifacts.save("baselines", base, training_data=desc, features=["req_rate", "p95_s", "cpu_cores", "mem_bytes",
                                                                       "error_ratio", "cpu_per_req"], extra=meta)
        artifacts.save("detectors", det_final, training_data=desc, features=DET_FEATURES, extra=meta)
        artifacts.save("classifier", FaultClassifier(cls_final, CLS_FEATURES, list(cls_final.classes_), tau, gate_final),
                       training_data=desc, features=CLS_FEATURES, extra=meta)
        artifacts.save("ranker", Ranker(ranker_model), training_data=desc, features=EVIDENCE, extra=meta)
        print(f"\nartifacts saved to {artifacts.ARTIFACT_DIR}")


if __name__ == "__main__":
    main()
