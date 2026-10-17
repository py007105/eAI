"""B1: sanity-check the collected live runs BEFORE any training.

    python models/check_runs.py [--runs data/runs] [--reps 8] [--out docs/results/runs_sanity.md]

1. Completeness: every (scenario, repetition) present; per-scenario counts; missing seeds listed.
2. Corruption: each run's data must cover the pre- and post-injection windows, and the injected fault must be
   VISIBLE in the target service's signals (a run where it is not visible is flagged, not silently kept).
   Flagged runs are written to data/runs/EXCLUDED.json with the reason; training skips them.
3. Leakage: no scenario name, injection flag or ground-truth field may appear in the raw signal columns or in the
   model feature lists.
4. Order/drift: run order (by injection time) must not predict the label or drift the healthy baseline.
"""
import argparse
import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import chi2_contingency, kruskal, spearmanr
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupKFold
from sklearn.tree import DecisionTreeClassifier

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from collect_runs import SCENARIOS  # noqa: E402

from eternalai import config  # noqa: E402
from eternalai.detect import FEATURES as DET_FEATURES  # noqa: E402
from eternalai.features.window import FEATURE_NAMES  # noqa: E402

warnings.filterwarnings("ignore")
HEALTHY = {"traffic_surge", "good_deploy"}
BANNED_SUBSTRINGS = ["scenario", "inject", "chaos", "truth", "target", "seed", "label", "expected", "crash", "leak",
                     "bad_deploy", "good_deploy", "cpu_burn", "surge", "run_id"]
# Samples are 2 s apart. The default 45 s run timeout saves about 34 s (13 samples) of post-injection data by
# design, so 10 samples (20 s) is the completeness floor. A first version of this check used 15 and flagged 17
# runs only for being 12-14 samples long; that threshold was stricter than the collection design and was
# lowered after seeing that first pass (recorded here, and in docs/DATA.md).
MIN_POST_SAMPLES = 10
# The evaluator waits 45 s after a restore, but errors from the restore tail persist until about 40 s before injection:
# pooled over all runs the error ratio is 0.148 / 0.040 / 0.003 / 0.000 for the 5 s bins starting at -50 / -45 / -40 / -35
# (scripts/debug_settle.py). The clean pre-injection period is therefore [t0-40 s, t0-5 s].
CLEAN_PRE_S = 40
TRUTH_FIELDS = ["run_id", "scenario", "target", "expected_label", "supported", "t_inject", "params", "seed"]


def window(df, a, b):
    return df[(df.index >= a) & (df.index <= b)]


def med(s):
    s = s.dropna()
    return float(s.median()) if len(s) else np.nan


def signature(scen, df, t0, web):
    """(visible: bool, evidence: str) for the injected fault in the target service frame `df`."""
    pre, post = window(df, t0 - 60, t0 - 5), window(df, t0 + 10, t0 + 50)
    if len(post) < 8:
        return False, "fewer than 8 post-injection samples"
    err_ratio = lambda w: float(w.err_rate.sum() / w.req_rate.sum()) if w.req_rate.sum() > 0 else np.nan
    if scen == "crash":
        down = float((post.up.fillna(0) < 0.5).mean())
        return down > 0.5, f"target not up in {down:.0%} of post samples"
    if scen == "latency":
        a, b = med(pre.p95_s), med(post.p95_s)
        return bool(b > max(3 * a, 0.3)), f"p95 median {a:.3f}s -> {b:.3f}s"
    if scen == "error_spike":
        a, b = err_ratio(pre), err_ratio(post)
        return bool(b > 0.15), f"error ratio {a:.3f} -> {b:.3f}"
    if scen == "memory_leak":
        grow = med(post.mem_bytes) - med(pre.mem_bytes)
        died = float((post.up.fillna(0) < 0.5).mean()) > 0.3  # an OOM-killed target is a valid outcome
        return bool(grow > 20e6 or died), f"memory +{grow / 1e6:.0f} MB; target died: {died}"
    if scen == "disk_fill":
        grow = float(post.scratch_bytes.max() - med(pre.scratch_bytes))
        return bool(grow > 20e6), f"scratch +{grow / 1e6:.0f} MB"
    if scen == "bad_deploy":
        dep, e = float(post.deploys_3m.max()), err_ratio(post)
        return bool(dep >= 1 and e > 0.15), f"deploys_3m max {dep:.0f}; error ratio {e:.3f}"
    if scen == "cpu_burn":
        a, b = med(pre.cpu_cores), med(post.cpu_cores)
        return bool(b > 1.5 * a), f"cpu {a:.3f} -> {b:.3f} cores"
    if scen == "traffic_surge":
        wpre, wpost = window(web, t0 - 60, t0 - 5), window(web, t0 + 10, t0 + 50)
        a, b = med(wpre.req_rate), med(wpost.req_rate)
        return bool(b > 1.8 * a), f"web req_rate {a:.1f} -> {b:.1f}/s"
    if scen == "good_deploy":
        dep = float(post.deploys_3m.max())
        return dep >= 1, f"deploys_3m max {dep:.0f}"
    return False, "unknown scenario"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", default="data/runs")
    ap.add_argument("--reps", type=int, default=8)
    ap.add_argument("--out", default="docs/results/runs_sanity.md")
    a = ap.parse_args()
    runs_dir = Path(a.runs)
    R = ["# Collected-runs sanity check (B1)\n", "Generated by `models/check_runs.py` before any model was trained.\n"]

    # ---- 1. completeness
    runs = []
    for js in sorted(runs_dir.glob("*.json")):
        truth = json.loads(js.read_text())
        csv = js.with_suffix(".csv")
        if not csv.exists():
            R.append(f"- {js.stem}: truth file present but CSV missing")
            continue
        runs.append({"id": js.stem, "truth": truth, "raw": pd.read_csv(csv, index_col=[0, 1])})
    expected = {f"{s}_{1000 + rep * 100 + i}" for rep in range(a.reps) for i, s in enumerate(SCENARIOS)}
    have = {r["id"] for r in runs}
    missing = sorted(expected - have)
    R.append("## 1. Completeness\n")
    R.append(f"- runs found: {len(have)} of {len(expected)} planned; missing: {len(missing)}")
    cnt = pd.Series([r["truth"]["scenario"] for r in runs]).value_counts().reindex(SCENARIOS).fillna(0).astype(int)
    R.append("\n| scenario | runs | planned |\n|---|---|---|\n" + "\n".join(f"| {s} | {n} | {a.reps} |" for s, n in cnt.items()))
    R.append(f"\nMissing seeds: {missing or 'none'}")
    tgt = pd.crosstab(pd.Series([r["truth"]["scenario"] for r in runs]), pd.Series([r["truth"]["target"] for r in runs]),
                      rownames=["scenario"], colnames=["target"])
    R.append("\nTargets chosen per scenario (random, by the evaluator):\n\n" + tgt.to_markdown())

    # ---- 2. corruption
    R.append("\n## 2. Corruption and visibility of the injected fault\n")
    rows, excluded = [], {}
    for r in runs:
        t, raw = r["truth"], r["raw"]
        t0, scen, tg = t["t_inject"], t["scenario"], t["target"]
        reasons = []
        svcs = set(raw.index.get_level_values(0))
        if svcs != set(config.SERVICES):
            reasons.append(f"services present {sorted(svcs)}")
        frame = raw.loc[tg] if tg in svcs else pd.DataFrame()
        web = raw.loc["web"] if "web" in svcs else pd.DataFrame()
        if not frame.empty:
            # The CLEAN pre-injection period is [t0-45 s, t0-5 s]: the evaluator waits >= 45 s after restoring the stack,
            # so earlier saved data overlaps the restore of the previous run (see docs/DATA.md, "restore contamination").
            pre_n = int(((frame.index >= t0 - CLEAN_PRE_S) & (frame.index < t0 - 5)).sum())
            post_n = int(((frame.index >= t0 + 8) & (frame.index <= t0 + 60)).sum())
            if pre_n < 15:
                reasons.append(f"only {pre_n} clean pre-injection samples")
            if post_n < MIN_POST_SAMPLES:
                reasons.append(f"only {post_n} post-injection samples")
            nanfrac = float(window(frame, t0 - CLEAN_PRE_S, t0 - 5).req_rate.isna().mean())
            if nanfrac > 0.3 and scen != "crash":
                reasons.append(f"{nanfrac:.0%} of clean pre-injection req_rate missing (scrape gap)")
            # the stack must actually be healthy before the injection, for EVERY service
            for sv in svcs:
                w_ = window(raw.loc[sv], t0 - CLEAN_PRE_S, t0 - 5)
                den = float(w_.req_rate.sum())
                er = float(w_.err_rate.sum()) / den if den > 0 else 0.0
                if er > 0.05:
                    reasons.append(f"{sv} error ratio {er:.2f} before injection (stack not settled)")
                    break
            vis, ev = signature(scen, frame, t0, web)
            if not vis:
                reasons.append(f"fault not visible: {ev}")
        else:
            vis, ev = False, "no target frame"
            reasons.append("no target frame")
        rows.append((r["id"], scen, tg, "ok" if not reasons else "FLAG", ev, "; ".join(reasons)))
        if reasons:
            excluded[r["id"]] = "; ".join(reasons)
    df = pd.DataFrame(rows, columns=["run", "scenario", "target", "status", "evidence", "reason"])
    R.append(f"- runs flagged: {len(excluded)} of {len(runs)} (excluded from training, listed in data/runs/EXCLUDED.json)\n")
    R.append("Visible-fault evidence per run:\n\n" + df.drop(columns=["reason"]).to_markdown(index=False))
    if excluded:
        R.append("\nFlagged runs and why:\n\n" + "\n".join(f"- `{k}`: {v}" for k, v in excluded.items()))
    (runs_dir / "EXCLUDED.json").write_text(json.dumps(excluded, indent=1))

    # ---- 3. leakage
    R.append("\n## 3. Leakage checks\n")
    cols = set()
    for r in runs:
        cols |= set(r["raw"].columns)
    bad_cols = sorted(c for c in cols if any(b in c.lower() for b in BANNED_SUBSTRINGS) or c in TRUTH_FIELDS)
    bad_feats = sorted(f for f in set(FEATURE_NAMES) | set(DET_FEATURES) if any(b in f.lower() for b in BANNED_SUBSTRINGS))
    R.append(f"- raw signal columns ({len(cols)}): {sorted(cols)}")
    R.append(f"- raw columns containing a scenario name, injection flag or truth field: {bad_cols or 'none'}")
    R.append(f"- model feature names ({len(FEATURE_NAMES)}) containing such a word: {bad_feats or 'none'}")
    R.append(f"- truth fields available only to the evaluator: {TRUTH_FIELDS}; none are columns of the run CSVs: "
             f"{not (set(TRUTH_FIELDS) & cols)}")
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import train_models as tm  # noqa: E402
    forbidden_inputs = {"rel", "end", "run", "scenario", "target", "service", "label"} & set(tm.CLS_FEATURES)
    R.append(f"- bookkeeping columns (rel/end/run/scenario/target/service/label) among classifier inputs: "
             f"{sorted(forbidden_inputs) or 'none'}")
    R.append("- `deploys_3m` and `restarts_in_window` are derived from `app_release_seq` / `app_start_time_seconds`, which a "
             "production monitor can observe; they are not read from the evaluator.")

    # ---- 4. order and drift
    R.append("\n## 4. Run order and drift\n")
    ok = [r for r in runs if r["id"] not in excluded]
    order = sorted(ok, key=lambda r: r["truth"]["t_inject"])
    idx = {r["id"]: i for i, r in enumerate(order)}
    scen = np.array([r["truth"]["scenario"] for r in order])
    pos = np.arange(len(order))
    kw = kruskal(*[pos[scen == s] for s in SCENARIOS if (scen == s).any()])
    R.append(f"- Kruskal-Wallis of run position across scenarios: H={kw.statistic:.2f}, p={kw.pvalue:.3f} "
             f"(small p would mean some scenarios cluster early or late)")
    y = np.array([r["truth"]["scenario"] not in HEALTHY for r in order]).astype(int)
    rho, p_rho = spearmanr(pos, y)
    third = np.array_split(np.arange(len(y)), 3)
    R.append(f"- Does run position predict fault-vs-healthy? Spearman rho={rho:+.3f}, p={p_rho:.3f}; share of fault runs by "
             f"third of the run order: {[round(float(y[t].mean()), 2) for t in third]} (overall {y.mean():.2f})")
    # Previous-scenario dependence by PERMUTATION test (a 9x9 table with <1 expected count per cell makes chi-square invalid)
    prev = np.array(["start"] + list(scen[:-1]))

    def stat(seq):
        pv = np.array(["start"] + list(seq[:-1]))
        ct_ = pd.crosstab(pv, seq).values.astype(float)
        exp = ct_.sum(1, keepdims=True) * ct_.sum(0, keepdims=True) / ct_.sum()
        return float(((ct_ - exp) ** 2 / np.where(exp > 0, exp, 1)).sum())
    obs = stat(scen)
    rng = np.random.default_rng(0)
    perm = [stat(rng.permutation(scen)) for _ in range(2000)]
    p_perm = float((np.array(perm) >= obs).mean())
    R.append(f"- Does the previous run's scenario predict the current one? permutation test (2000 shuffles of the run order, "
             f"chi-square statistic as the score): p={p_perm:.3f} (a large p means no detectable dependence)")
    R.append("\nBaseline drift: Spearman correlation between run position and each service's pre-injection median "
             "(clean window t0-40 s to t0-15 s):\n")
    drift = []
    for svc in config.SERVICES:
        for sig in ("p95_s", "cpu_cores", "mem_bytes", "req_rate"):
            xs, ys = [], []
            for r in order:
                if svc in r["raw"].index.get_level_values(0):
                    f = r["raw"].loc[svc]
                    xs.append(idx[r["id"]])
                    ys.append(med(window(f, r["truth"]["t_inject"] - CLEAN_PRE_S, r["truth"]["t_inject"] - 15)[sig]))
            xs, ys = np.array(xs), np.array(ys)
            ok_ = np.isfinite(ys)
            if ok_.sum() > 10:
                rho, p = spearmanr(xs[ok_], ys[ok_])
                drift.append((svc, sig, float(rho), float(p), bool(abs(rho) > 0.3 and p < 0.01)))
    dd = pd.DataFrame(drift, columns=["service", "signal", "spearman_rho", "p", "flag"])
    R.append(dd.round(3).to_markdown(index=False))
    flags = dd[dd.flag]
    R.append(f"\n- baseline-drift flags (|rho|>0.3 and p<0.01): {len(flags)}"
             + (" -> " + "; ".join(f"{r.service}.{r.signal}" for r in flags.itertuples()) if len(flags) else ""))

    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text("\n".join(R) + "\n", encoding="utf-8")
    print("\n".join(R[:60]))
    print(f"\nwrote {a.out}; flagged runs: {len(excluded)}")


if __name__ == "__main__":
    main()
