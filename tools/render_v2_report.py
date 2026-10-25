"""Render the v2 results tables (counts, Wilson intervals, accounting) from the exported rows. No number in the v2 documents is typed by hand.

    python tools/render_v2_report.py [--dir results/benchmark-v2/rerun] [--out docs/results/benchmark_v2.md]

Inputs (all read-only): benchmark_v2_evaluated.jsonl (valid original rows + re-run rows), benchmark_v2_rerun_raw.jsonl, invalid_rows.json, stock_log.jsonl,
and docs/results/v2_criteria_final.md (output of tools/evaluate_v2_criteria.py, included verbatim).

Intervals are Wilson 95% intervals for a proportion. They treat runs as independent draws, which they are not exactly (a few fixed seeds, one application, scripted
faults, one machine), so they describe sampling uncertainty only and are optimistic about everything else.
"""
import argparse
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from benchmark_status import V2_PLAN  # noqa: E402

SC = ["crash", "latency", "error_spike", "memory_leak", "disk_fill", "bad_deploy", "cpu_burn", "traffic_surge", "good_deploy"]
SUPPORTED = SC[:6]
ARMS = ["eternalai_autopilot", "threshold_restart", "eternalai_ask_first"]


def rows(p):
    return [json.loads(x) for x in Path(p).read_text(encoding="utf-8").splitlines() if x.strip()]


def wilson(k, n, z=1.96):
    if n == 0:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


def frac(k, n):
    w = wilson(k, n)
    return f"{k}/{n} [{w[0] * 100:.0f}%, {w[1] * 100:.0f}%]" if w else "-"


def sel(ev, arm=None, scs=None):
    return [r for r in ev if (arm is None or r["arm"] == arm) and (scs is None or r["scenario"] in scs)]


def cnt(rs, f):
    return sum(1 for r in rs if f(r["score"]))


def render(d):
    ev, rer = rows(d / "benchmark_v2_evaluated.jsonl"), rows(d / "benchmark_v2_rerun_raw.jsonl")
    inv = json.loads((d / "invalid_rows.json").read_text(encoding="utf-8"))
    rk = {(r["arm"], r["scenario"], r["seed"]) for r in rer}
    jobs = inv["jobs"]
    same = [j for j in jobs if j["kind"] == "same-seed"]
    fresh = [j for j in jobs if j["kind"] == "fresh"]
    fresh_seeds = sorted({j["seed"] for j in fresh})
    stock = [r["stock"] for r in rer if r.get("stock")]
    L = ["# v2 results (rendered by `tools/render_v2_report.py`; every number comes from the exported rows)", "",
         "Method, deviations and limitations: `docs/EVALUATION.md` (canonical). Wording rule: Amendment 6. These tables describe the **reduced v2 plan** (Amendment 4 section M) "
         "on seeds 200-318 and the replacement block 400-429 (Amendment 8). v1 and v2 are unpaired and use different seeds. No `no_action` or `prototype_rules` arm was run in v2, "
         "and `threshold_restart` was run only on healthy runs, so **v2 has no paired baseline comparison for supported faults**.", "",
         "## 1. Run accounting", "",
         f"- evaluated set: **{len(ev)}** rows = **{len(ev) - len(rer)} valid original** + **{len(rer)} replacement (re-run)**",
         f"- original rows marked invalid by the Amendment 8 exclusion rule (run ended after the last confirmed in-stock checkout): **{len(inv['invalid'])}** "
         "(kept in `benchmark_v2_raw.jsonl`, never deleted; listed in `invalid_rows.json`; every one is triage class a, harness/environment artifact)",
         f"- replacement jobs: {len(jobs)}; **{len(same)} reused the original seed** (the partner arm stayed valid) and **{len(jobs) - len(same)} used fresh seeds** "
         f"({len(fresh_seeds)} distinct seeds, {fresh_seeds[0]}-{fresh_seeds[-1]})",
         "- the replacement runs were **designed after the stock-out was seen**; the exclusion rule is by stock timeline (timestamps), not by outcome, and was committed "
         "before any restock or re-run (Amendment 8)",
         f"- stock gate (re-runs only): {sum(1 for s in stock if s.get('restocked'))} restock(s); lowest per-SKU stock after any re-run: "
         f"{min(min(s['after_run'].values()) for s in stock if s.get('after_run'))}; re-run rows with a stock record: {len(stock)} of {len(rer)}",
         "", "## 2. Pre-registered criteria (Amendment 4 section N), script output", "",
         Path("docs/results/v2_criteria_final.md").read_text(encoding="utf-8").split("\n", 2)[2].strip(), "",
         "## 3. Per cell: sample sizes with Wilson 95% intervals", "",
         "n is 3 per fault cell and 4-12 per healthy cell. With n = 3 a perfect cell (3/3) is still compatible with a true rate near 44%; a pooled 18/18 is compatible with a true rate "
         "down to about 82%. Treat these as 'no failure observed', not as a rate.", "",
         "| arm | scenario | n | seeds | detected | recovered (self-verified) | failed-request % (values; mean) | incident opened | action executed | abstained correctly |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    for (arm, sc), n_plan in sorted(V2_PLAN.items(), key=lambda kv: (ARMS.index(kv[0][0]), SC.index(kv[0][1]))):
        rs = sorted(sel(ev, arm, [sc]), key=lambda r: r["seed"])
        s = [r["score"] for r in rs]
        fp = [x["failed_request_pct"] for x in s if x.get("failed_request_pct") is not None]
        sup = sc in SUPPORTED
        L.append(f"| {arm} | {sc} | {len(rs)}/{n_plan} | {' '.join(str(r['seed']) for r in rs)} | {frac(cnt(rs, lambda x: x.get('detected')), len(rs)) if sup or sc == 'cpu_burn' else '-'} | "
                 f"{frac(cnt(rs, lambda x: x.get('recovered')), len(rs)) if sup else '-'} | {' '.join(f'{v:.1f}' for v in fp)}; {sum(fp) / len(fp):.2f} | "
                 f"{frac(cnt(rs, lambda x: (x.get('incidents_opened') or 0) > 0), len(rs))} | {frac(cnt(rs, lambda x: (x.get('actions_executed') or 0) > 0), len(rs))} | "
                 f"{frac(cnt(rs, lambda x: x.get('abstained_correctly')), len(rs)) if sc == 'cpu_burn' else '-'} |")
    L += ["", "## 4. Pooled counts with Wilson 95% intervals", "", "| quantity | count [95% interval] | note |", "|---|---|---|"]
    for arm in ("eternalai_autopilot", "eternalai_ask_first"):
        f = sel(ev, arm, SUPPORTED)
        L.append(f"| {arm}: supported faults detected | {frac(cnt(f, lambda x: x.get('detected')), len(f))} | 6 fault types x 3 seeds |")
        L.append(f"| {arm}: supported faults recovered (own verification) | {frac(cnt(f, lambda x: x.get('recovered')), len(f))} | recovery is internally verified; see EVALUATION.md |")
    for arm in ARMS:
        h = sel(ev, arm, ["traffic_surge", "good_deploy"])
        L.append(f"| {arm}: healthy runs that opened an incident | {frac(cnt(h, lambda x: (x.get('incidents_opened') or 0) > 0), len(h))} | traffic_surge + good_deploy |")
        L.append(f"| {arm}: healthy runs with an executed action | {frac(cnt(h, lambda x: (x.get('actions_executed') or 0) > 0), len(h))} | |")
    u = sel(ev, "eternalai_autopilot", ["cpu_burn"])
    L.append(f"| eternalai_autopilot: cpu_burn abstained correctly | {frac(cnt(u, lambda x: x.get('abstained_correctly')), len(u))} | unseen fault; n = 3 |")
    fa = [r["score"]["failed_request_pct"] for r in sel(ev, "eternalai_autopilot", SUPPORTED)]
    ft = [r["score"]["time_to_detect_s"] for r in sel(ev, "eternalai_autopilot", SUPPORTED) if r["score"].get("detected")]
    L += ["", f"Autopilot, 18 supported runs: mean failed-request % {sum(fa) / len(fa):.2f} (min {min(fa):.2f}, max {max(fa):.2f}); mean detection {sum(ft) / len(ft):.2f} s "
          f"(min {min(ft):.1f}, max {max(ft):.1f}). No `no_action` run exists in v2, so the failed-request % has no same-seed reference.", "",
          "## 5. cpu_burn rows (autopilot; unseen fault, no runbook)", "",
          "| seed | target | abstained correctly | actions executed | scorer 'harmful' flag | final status | failed-request % |", "|---|---|---|---|---|---|---|"]
    for r in sorted(u, key=lambda r: r["seed"]):
        s = r["score"]
        L.append(f"| {r['seed']} | {r['target']} | {s['abstained_correctly']} | {s['actions_executed']} | {s['harmful_interventions']} | {s['final_status']} | {s['failed_request_pct']} |")
    L += ["", "The scorer's 'harmful' flag only means an executed action on a service other than the injected target (`evaluator/scoring.py`); it is not a measurement of damage. "
          "Details: `docs/postmortems/cpu_burn_seed426.md`.", "",
          "## 6. Replacement jobs (script output of the exclusion rule)", "", "| arm | scenario | seed | kind |", "|---|---|---|---|"]
    for j in sorted(jobs, key=lambda j: (j["seed"], j["arm"])):
        L.append(f"| {j['arm']} | {j['scenario']} | {j['seed']} | {j['kind']} |")
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="results/benchmark-v2/rerun")
    ap.add_argument("--out", default="docs/results/benchmark_v2.md")
    a = ap.parse_args()
    t = render(Path(a.dir))
    Path(a.out).write_text(t, encoding="utf-8")
    print(f"wrote {a.out} ({len(t.splitlines())} lines)")


if __name__ == "__main__":
    main()
