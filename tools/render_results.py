"""Render every benchmark table from the raw rows. No number in the results documents is typed by hand.

    python tools/render_results.py [--raw docs/results/benchmark_raw.jsonl] [--raw-v2 PATH] [--out docs/results/benchmark.md]
                                     [--triage docs/postmortems/triage.json] [--harness-failures docs/results/harness_failures.json]
                                     [--fixture]

Rules implemented here (from docs/EVALUATION_PLAN.md): every cell shows all raw values with mean and min-max; bootstrap 95% intervals only for
POOLED metrics, resampled by run (by seed for paired differences); no significance claims between arms from n = 5 per cell; every run is kept; every
non-recovery is listed with its triage class; v1 and v2 side by side when a v2 file is given.

`--fixture` marks the output "FIXTURE DATA, NOT RESULTS" and refuses to write to the real results path; the tests use it with synthetic rows only.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ARMS = ["no_action", "threshold_restart", "prototype_rules", "eternalai_ask_first", "eternalai_autopilot"]
SUPPORTED = ["crash", "latency", "error_spike", "memory_leak", "disk_fill", "bad_deploy"]
UNSEEN, HEALTHY = ["cpu_burn"], ["traffic_surge", "good_deploy"]
SCENARIOS = SUPPORTED + UNSEEN + HEALTHY
REPS = 5
REAL_OUT = "docs/results/benchmark.md"
FIXTURE_BANNER = "> **FIXTURE DATA, NOT RESULTS.** Synthetic rows used only to test this renderer. Nothing below describes the system.\n"


def load(path):
    rows = []
    for line in Path(path).read_text().splitlines():
        r = json.loads(line)
        s = r["score"]
        rows.append({"arm": r["arm"], "scenario": r["scenario"], "seed": r["seed"], "rep": r.get("rep"), "target": r.get("target"),
                     "detected": s.get("detected"), "detect_s": s.get("time_to_detect_s"), "top1": s.get("diagnosis_top1"),
                     "top3": s.get("diagnosis_top3"), "recovered": s.get("recovered"), "ttvr_s": s.get("time_to_verified_recovery_s"),
                     "failed_pct": s.get("failed_request_pct"), "false_alerts": s.get("false_alerts"),
                     "harmful": s.get("harmful_interventions"), "abstained_ok": s.get("abstained_correctly"),
                     "incidents": s.get("incidents_opened"), "actions": s.get("actions_executed"), "final": s.get("final_status"),
                     "commit": r.get("system_commit"),
                     "llm_lines": sum("report by " in json.dumps(i.get("timeline")) for i in (r.get("incidents") or []))})
    df = pd.DataFrame(rows)
    return df.drop_duplicates(["arm", "scenario", "seed"], keep="last").reset_index(drop=True)      # each seed counted once per arm


def boot_ci(values, n=2000, seed=0):
    v = np.asarray([x for x in values if x is not None and not pd.isna(x)], dtype=float)
    if len(v) < 2:
        return None
    rng = np.random.default_rng(seed)
    means = [rng.choice(v, len(v), replace=True).mean() for _ in range(n)]
    return float(v.mean()), float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5)), len(v)


def fmt_ci(ci, pct=False, d=2):
    if ci is None:
        return "-"
    m, lo, hi, n = ci
    k = 100 if pct else 1
    return f"{m * k:.{d}f} [{lo * k:.{d}f}, {hi * k:.{d}f}] (n={n})"


def vals(series, d=1, boolean=False):
    out = []
    for x in series:
        out.append("-" if x is None or pd.isna(x) else (str(int(bool(x))) if boolean else f"{x:.{d}f}"))
    return " ".join(out)


def mm(series, d=1):
    s = pd.Series([x for x in series if x is not None and not pd.isna(x)], dtype=float)
    return ("-", "-") if s.empty else (f"{s.mean():.{d}f}", f"{s.min():.{d}f} to {s.max():.{d}f}")


def per_cell(d, arms, title, col, scenarios, d_=1, boolean=False, only=None):
    R = [f"\n### {title}\n", "All raw values in seed order (repetition 0..4), then mean and min to max. `-` = not defined for that run.\n",
         "| scenario | arm | values | mean | min to max | n |", "|---|---|---|---|---|---|"]
    for sc in scenarios:
        for arm in arms:
            x = d[(d.arm == arm) & (d.scenario == sc)].sort_values("seed")
            if x.empty:
                continue
            ser = x[col].astype(object).where(x[col].notna(), None)
            if boolean:
                m = ser.dropna().astype(float)
                mean_s, rng_s = (f"{m.mean():.2f}", f"{int(m.min())} to {int(m.max())}") if len(m) else ("-", "-")
            else:
                mean_s, rng_s = mm(ser, d_)
            R.append(f"| {sc} | {arm} | {vals(ser, d_, boolean)} | {mean_s} | {rng_s} | {len(x)} |")
    return R


def pooled(d, arm):
    x = d[d.arm == arm]
    f, h, u = x[x.scenario.isin(SUPPORTED)], x[x.scenario.isin(HEALTHY)], x[x.scenario.isin(UNSEEN)]
    rec = f.recovered.fillna(False).astype(float)
    return {"arm": arm, "supported runs": len(f),
            "failed requests % (supported runs; independent measure)": fmt_ci(boot_ci(f.failed_pct), d=2),
            "recovery rate, self-reported": fmt_ci(boot_ci(rec), pct=True, d=1) if len(rec) else "-",
            "seconds to self-reported recovery (recovered runs)": fmt_ci(boot_ci(f.ttvr_s[f.recovered == True]), d=1),
            "detection time s (detected runs)": fmt_ci(boot_ci(f.detect_s[f.detected == True]), d=1),
            "root-cause top-1": f"{int(f.top1.fillna(False).astype(bool).sum())}/{len(f)}" if arm != "no_action" else "-",
            "root-cause top-3": f"{int(f.top3.fillna(False).astype(bool).sum())}/{len(f)}" if arm != "no_action" else "-",
            "healthy runs with a false alert": f"{int((h.false_alerts.fillna(0) > 0).sum())}/{len(h)}",
            "harmful interventions (all runs)": int(x.harmful.fillna(0).sum()),
            "unseen fault: abstained correctly": f"{int(u.abstained_ok.fillna(False).astype(bool).sum())}/{len(u)}",
            "unseen fault: self-reported recovery": f"{int(u.recovered.fillna(False).astype(bool).sum())}/{len(u)}"}


def headline(d, arms):
    """Compact all-arms comparison: pooled over supported faults, healthy-run behaviour, and one row per supported scenario."""
    R, rows = [], []
    for a in arms:
        x = d[d.arm == a]
        f, h = x[x.scenario.isin(SUPPORTED)], x[x.scenario.isin(HEALTHY)]
        rec = f.recovered.fillna(False).astype(bool)
        rows.append({"arm": a, "failed-request % (mean, 30 supported runs)": f"{f.failed_pct.mean():.2f}",
                     "self-reported recovery": f"{int(rec.sum())}/{len(f)}",
                     "seconds to self-reported recovery (mean, recovered runs)": f"{f.ttvr_s[rec].mean():.1f}" if rec.any() else "-",
                     "healthy runs with a false alert": f"{int((h.false_alerts.fillna(0) > 0).sum())}/{len(h)}",
                     "harmful interventions on healthy runs": int(h.harmful.fillna(0).sum()),
                     "harmful interventions, all runs": int(x.harmful.fillna(0).sum())})
    R.append(pd.DataFrame(rows).to_markdown(index=False))
    R.append("\nPer supported scenario (5 runs per cell): self-reported recovery k/5, mean failed-request %, mean seconds to self-reported recovery.\n")
    cells = []
    for sc in SUPPORTED:
        row = {"scenario": sc}
        for a in arms:
            c = d[(d.arm == a) & (d.scenario == sc)]
            rec = c.recovered.fillna(False).astype(bool)
            ttr = f"{c.ttvr_s[rec].mean():.0f}s" if rec.any() else "-"
            row[a] = f"{int(rec.sum())}/{len(c)}; {c.failed_pct.mean():.1f}%; {ttr}"
        cells.append(row)
    R.append(pd.DataFrame(cells).to_markdown(index=False))
    return R


READING_GUIDE = [
    "**How to read this document**\n",
    "1. The **failed-request %** (section 2) is the independent measure: the evaluator reads it from the load generator, not from the system under test.",
    "2. **Recovery is self-reported.** It comes from the system's own synthetic-checkout verification. It is never independently verified in v1; no raw probe logs exist. "
    "The consistency check in section 2 compares claimed recoveries with the no-action arm for the same seed.",
    "3. **LLM path.** The benchmark brains were configured without LLM keys (by construction), so reports are expected to be template reports. The report provider is not "
    "recorded in the rows (design limitation, class c); section 1 counts incident timelines that contain a `report by <provider>` line, which the engine writes only for a non-template provider.\n",
]


def consistency_lines(d, arms):
    if "no_action" not in arms:
        return ["- not computable: no `no_action` rows"]
    na = d[d.arm == "no_action"].set_index("seed").failed_pct
    bad = d[(d.arm != "no_action") & (d.recovered == True) & d.scenario.isin(SUPPORTED)]
    lines = [f"- {r.arm} / {r.scenario} / seed {r.seed}: claimed recovered with {r.failed_pct:.2f}% failed vs {na[r.seed]:.2f}% with no action"
             for r in bad.itertuples() if r.seed in na.index and pd.notna(r.failed_pct) and pd.notna(na[r.seed]) and r.failed_pct > na[r.seed]]
    checked = sum(1 for r in bad.itertuples() if r.seed in na.index)
    return [f"A claimed recovery should come with a failed-request % no higher than the `no_action` arm's value for the same seed. "
            f"Claimed recoveries compared: {checked}. Violations, one per line:\n"] + (lines or ["- none"])


def paired_diff(d, a, b, col, scenarios, as_rate=False, n=2000, seed=0):
    piv = d[d.scenario.isin(scenarios)].pivot_table(index="seed", columns="arm", values=col, aggfunc="first")
    if a not in piv or b not in piv:
        return None
    x = piv[[a, b]].dropna().astype(float)
    if len(x) < 3:
        return None
    diff = (x[a] - x[b]).to_numpy()
    rng = np.random.default_rng(seed)
    means = [rng.choice(diff, len(diff), replace=True).mean() for _ in range(n)]
    return float(diff.mean()), float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5)), len(diff)


def accounting(d, fails):
    R = ["\n## 1. Run accounting\n"]
    exp = len(ARMS) * len(SCENARIOS) * REPS
    got = d.drop_duplicates(["arm", "scenario", "seed"])
    R.append(f"- rows in the raw file: {len(d)}; distinct (arm, scenario, seed) runs: {len(got)} of {exp} planned; duplicate rows: {len(d) - len(got)}")
    miss = []
    for arm in ARMS:
        for sc in SCENARIOS:
            n = len(got[(got.arm == arm) & (got.scenario == sc)])
            if n != REPS:
                miss.append(f"{arm}/{sc}: {n}/{REPS}")
    R.append(f"- cells not at {REPS} runs: {miss or 'none'}")
    R.append(f"- system commit recorded in rows: {d.groupby('arm').commit.unique().apply(list).to_dict()}")
    n_llm = int((got.llm_lines > 0).sum())
    R.append(f"- runs whose recorded incident timelines contain a `report by <provider>` line (non-template report): {n_llm} of {len(got)}. "
             "Zero is consistent with template-only reports but is not a direct record; the provider is not stored per row.")
    R.append("- no run was dropped: every row enters every table below. Rows are never filtered.")
    if fails:
        R.append("\nHarness failures (attempts kept; the re-run with the same seed is in the tables above):\n")
        R.append("| arm | scenario | seed | attempt | criterion | evidence |\n|---|---|---|---|---|---|")
        R += [f"| {f['arm']} | {f['scenario']} | {f['seed']} | {f.get('attempt', 1)} | {f['criterion']} | {f['evidence']} |" for f in fails]
    else:
        R.append("- harness failures recorded: none listed in the failures file")
    return R


def completeness(d):
    """(complete, distinct runs, markdown table of runs per arm x scenario)."""
    got = d.drop_duplicates(["arm", "scenario", "seed"])
    cnt = got.groupby(["arm", "scenario"]).size().unstack(fill_value=0).reindex(index=ARMS, columns=SCENARIOS, fill_value=0)
    tab = cnt.reset_index().rename(columns={"arm": "arm (runs per scenario, planned %d)" % REPS}).to_markdown(index=False)
    return bool((cnt == REPS).all().all()), len(got), tab


def incomplete_banner(n_runs, tab):
    exp = len(ARMS) * len(SCENARIOS) * REPS
    return [f"> **INCOMPLETE: {n_runs} of {exp} planned runs.** This document was rendered before the benchmark finished. Arms and cells differ in how many runs they contain, "
            "so pooled rows compare arms on different scenarios and seeds and must not be read as a ranking. Paired differences use only seeds present in both arms. "
            "Nothing here is the final result.\n", "Runs present per cell:\n", tab, ""]


V2_BANNER = ("> **v1 and v2 are UNPAIRED and use DIFFERENT SEEDS** (v1 100-148, v2 200-318). v2 differs from v1 in four things at once: the retrained models, the memory "
             "features, the approval-queue fix and the telemetry condition (T3: trace exporter off, no collector; the v1 benchmark ran with the exporter on and the collector dead). "
             "**No difference below can be attributed to any single change**; v2 is described only as fixes for the failures v1 exposed, tested on fresh seeds. "
             "Recovery is self-reported in both. v2 is a reduced plan: the run counts are shown with every figure; with these sample sizes small differences, per-scenario "
             "effects and any comparison on faults with the `no_action` / `prototype_rules` baselines (not run in v2) cannot be shown.\n")


def _side(x):
    f, h, u = x[x.scenario.isin(SUPPORTED)], x[x.scenario.isin(HEALTHY)], x[x.scenario.isin(UNSEEN)]
    rec = f.recovered.fillna(False).astype(bool)
    det = f.detect_s[f.detected == True]
    return {"supported runs": len(f), "recovered (self-reported)": f"{int(rec.sum())}/{len(f)}" if len(f) else "-",
            "detected": f"{int((f.detected == True).sum())}/{len(f)}" if len(f) else "-",
            "mean detection s": f"{det.mean():.1f}" if len(det) else "-",
            "mean failed-request %": f"{f.failed_pct.mean():.2f}" if len(f) else "-",
            "healthy runs": len(h),
            "healthy runs with an incident": f"{int((h.incidents.fillna(0) > 0).sum())}/{len(h)}" if len(h) else "-",
            "healthy runs with an executed action": f"{int((h.actions.fillna(0) > 0).sum())}/{len(h)}" if len(h) else "-",
            "cpu_burn abstained correctly": f"{int(u.abstained_ok.fillna(False).astype(bool).sum())}/{len(u)}" if len(u) else "-"}


def v2_section(d, d2):
    R = ["\n## 8. v1 and v2 side by side\n", V2_BANNER,
         "v1 rows above are never replaced. Same definitions for both versions; counts are k/n over the runs that exist for that arm and version.\n"]
    both = []
    for a in ARMS:
        for ver, x in (("v1", d), ("v2", d2)):
            xa = x[x.arm == a]
            if len(xa):
                both.append({"arm": a, "version": ver, **_side(xa)})
    R.append(pd.DataFrame(both).to_markdown(index=False))
    return R


def render(d, d2, triage, fails, fixture):
    arms = [a for a in ARMS if a in set(d.arm)]
    R = ["# Held-out benchmark results" + (" (FIXTURE)" if fixture else ""), ""]
    if fixture:
        R.append(FIXTURE_BANNER)
    complete, n_runs, tab = completeness(d)
    if not complete:
        R += incomplete_banner(n_runs, tab)
    R.append("Rendered by `tools/render_results.py` from the raw rows. Method and rules: `docs/EVALUATION_PLAN.md` (including Amendment 1). Cells with n = 5 are not compared "
             "for significance; intervals are bootstrap 95% over runs and are shown only for pooled metrics.\n")
    R += READING_GUIDE
    R += accounting(d, fails)

    R.append("\n## 1b. Headline comparison, all arms side by side\n")
    R += headline(d, arms)

    R.append("\n## 2. The independent measure first: failed-request %\n")
    R.append("Computed by the evaluator from the load generator's counters between injection and the end of the observation window. It does not depend on what "
             "the system under test reports.\n")
    R += per_cell(d, arms, "Failed-request %, per cell (all scenarios)", "failed_pct", SUPPORTED + UNSEEN + HEALTHY, d_=2)
    R.append("\n### Consistency check of self-reported recovery against the no-action arm\n")
    R += consistency_lines(d, arms)

    R.append("\n## 3. Everything else per cell (reported by the system under test or derived from its incident log)\n")
    R += per_cell(d, arms, "Recovery, SELF-REPORTED by the system's own checkout verification (1 = recovered, 0 = not), supported fault scenarios", "recovered",
                  SUPPORTED, boolean=True)
    R += per_cell(d, arms, "Seconds to self-reported recovery (recovered runs only)", "ttvr_s", SUPPORTED)
    R += per_cell(d, arms, "Detection time, seconds (detected runs only)", "detect_s", SUPPORTED + UNSEEN)
    R += per_cell(d, arms, "Root-cause top-1 (1 = injected service ranked first)", "top1", SUPPORTED, boolean=True)
    R += per_cell(d, arms, "False alerts on healthy runs (incidents opened)", "false_alerts", HEALTHY, d_=0)
    R += per_cell(d, arms, "Harmful interventions (executed actions on a service other than the target; any action in a healthy run)", "harmful",
                  SUPPORTED + UNSEEN + HEALTHY, d_=0)
    R += per_cell(d, arms, "Unseen fault: abstained correctly (1 = yes)", "abstained_ok", UNSEEN, boolean=True)
    R += per_cell(d, arms, "Unseen fault: self-reported recovery (not expected from EternalAI by design)", "recovered", UNSEEN, boolean=True)

    R.append("\n## 4. Pooled metrics per arm (bootstrap 95% interval over runs)\n")
    R.append(pd.DataFrame([pooled(d, a) for a in arms]).to_markdown(index=False))

    me = [a for a in ("eternalai_autopilot", "eternalai_ask_first") if a in arms]
    R.append("\n## 5. Pooled paired differences (same seeds; mean difference with bootstrap 95% interval over seeds)\n")
    R.append("Negative is better for times and failed-request %, positive is better for recovery. `interval excludes zero` is a statement about the "
             "interval only; it is not a significance test and the plan makes no claim from it for individual cells.\n")
    rows = []
    for a in me:
        for b in [x for x in arms if x != a]:
            for label, col, better in (("failed requests % (supported)", "failed_pct", "low"), ("self-reported recovery (supported)", "recovered", "high"),
                                       ("seconds to self-reported recovery", "ttvr_s", "low"), ("detection time s", "detect_s", "low")):
                dd = d.copy()
                if col == "recovered":
                    dd[col] = dd[col].fillna(False).astype(float)
                p = paired_diff(dd, a, b, col, SUPPORTED)
                if p:
                    rows.append({"arm": a, "versus": b, "metric": label, "mean diff": round(p[0], 3),
                                 "95% interval": f"[{p[1]:.3f}, {p[2]:.3f}]", "paired seeds": p[3],
                                 "interval excludes zero": bool(p[1] > 0 or p[2] < 0), "direction": "favours " + (a if (p[0] < 0) == (better == "low") else b)})
    R.append(pd.DataFrame(rows).to_markdown(index=False) if rows else "- not enough paired data")

    R.append("\n## 6. Metrics on which EternalAI is not ahead of an arm (pooled point estimates, plain list)\n")
    pr = {a: pooled(d, a) for a in arms}
    notes = []
    for a in me:
        for b in [x for x in arms if x != a]:
            pa, pb = d[(d.arm == a) & d.scenario.isin(SUPPORTED)], d[(d.arm == b) & d.scenario.isin(SUPPORTED)]
            for label, fa, fb, lower in (("failed requests %", pa.failed_pct.mean(), pb.failed_pct.mean(), True),
                                         ("self-reported recovery rate", pa.recovered.fillna(False).astype(float).mean(),
                                          pb.recovered.fillna(False).astype(float).mean(), False),
                                         ("detection time s", pa.detect_s[pa.detected == True].mean(), pb.detect_s[pb.detected == True].mean(), True),
                                         ("seconds to self-reported recovery", pa.ttvr_s[pa.recovered == True].mean(), pb.ttvr_s[pb.recovered == True].mean(), True)):
                if pd.notna(fa) and pd.notna(fb) and ((fa >= fb) if lower else (fa <= fb)):
                    notes.append(f"- {label}: {a} {fa:.2f} versus {b} {fb:.2f}")
    R += notes or ["- none by pooled point estimate"]

    R.append("\n## 7. Every non-recovery and its triage class\n")
    R.append("All supported-fault runs with `recovered` not true. Class from `docs/postmortems/triage.json`; a missing entry means unclassified (class a = harness artifact, "
             "b = system bug, c = design limitation).\n")
    tri = {(t["arm"], t["scenario"], t["seed"]): t for t in triage}
    bad = d[d.scenario.isin(SUPPORTED) & (d.recovered != True) & (d.arm != "no_action")]
    R.append("| arm | scenario | seed | final status | class | evidence |\n|---|---|---|---|---|---|")
    for r in bad.sort_values(["arm", "scenario", "seed"]).itertuples():
        t = tri.get((r.arm, r.scenario, r.seed), {})
        R.append(f"| {r.arm} | {r.scenario} | {r.seed} | {r.final} | {t.get('class', 'unclassified')} | {t.get('evidence', '-')} |")
    R.append(f"\n- non-recoveries: {len(bad)}; classified: {sum(1 for r in bad.itertuples() if (r.arm, r.scenario, r.seed) in tri)}")

    if d2 is not None:
        R += v2_section(d, d2)
    return "\n".join(R) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default="docs/results/benchmark_raw.jsonl")
    ap.add_argument("--raw-v2")
    ap.add_argument("--out", default=REAL_OUT)
    ap.add_argument("--triage", default="docs/postmortems/triage.json")
    ap.add_argument("--harness-failures", default="docs/results/harness_failures.json")
    ap.add_argument("--fixture", action="store_true")
    a = ap.parse_args()
    if a.fixture and Path(a.out).as_posix().endswith(REAL_OUT):
        sys.exit("refusing to write fixture output to the real results path")
    d = load(a.raw)
    d2 = load(a.raw_v2) if a.raw_v2 else None
    tri = json.loads(Path(a.triage).read_text()) if Path(a.triage).exists() else []
    fails = json.loads(Path(a.harness_failures).read_text()) if Path(a.harness_failures).exists() else []
    Path(a.out).write_text(render(d, d2, tri, fails, a.fixture), encoding="utf-8")
    print(f"wrote {a.out}")


if __name__ == "__main__":
    main()
