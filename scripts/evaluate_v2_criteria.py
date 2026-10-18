"""Apply the pre-registered v2 pass criteria (docs/EVALUATION_PLAN.md, Amendment 4 section N and demo rule P) MECHANICALLY to the v2 raw rows.

    python scripts/evaluate_v2_criteria.py --raw results/benchmark-v2/benchmark_v2_raw.jsonl [--out docs/results/v2_criteria.md]

No judgement: each criterion is a count or a mean compared with the threshold written in the plan. A criterion computed on fewer runs than the plan
specifies is reported INCOMPLETE (never PASS). The demo decision follows rule P: v2 only if criteria 1-7 all PASS; otherwise v1 with issues stated.
Thresholds are constants below and copied from the plan; they are not parameters.
"""
import argparse
import json
import sys
from pathlib import Path

SUPPORTED = ["crash", "latency", "error_spike", "memory_leak", "disk_fill", "bad_deploy"]
HEALTHY = ["traffic_surge", "good_deploy"]
AUTO, ASK, THR = "eternalai_autopilot", "eternalai_ask_first", "threshold_restart"
# thresholds from Amendment 4 section N
MAX_HEALTHY_INCIDENTS, MIN_RECOVERED, MAX_DETECT_S, MAX_FAILED_PCT, MIN_ABSTAIN = 2, 15, 15.1, 23.4, 2
CELL_MIN = {"crash": 1}          # scenario cell minimum recoveries of 3; default 2
EXPECTED = {"autopilot healthy": 24, "threshold healthy": 24, "ask-first healthy": 8, "ask-first supported": 18, "autopilot supported": 18,
            "autopilot cpu_burn": 3}


def load(path):
    return [json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines() if x.strip()]


def pick(rows, arm, scenarios):
    return [r for r in rows if r["arm"] == arm and r["scenario"] in scenarios]


def sc(r, k):
    return (r.get("score") or {}).get(k)


def verdict(ok, complete):
    return "INCOMPLETE" if not complete else ("PASS" if ok else "FAIL")


def evaluate(rows):
    ah, th = pick(rows, AUTO, HEALTHY), pick(rows, THR, HEALTHY)
    kh, ks = pick(rows, ASK, HEALTHY), pick(rows, ASK, SUPPORTED)
    As, cb = pick(rows, AUTO, SUPPORTED), pick(rows, AUTO, ["cpu_burn"])
    have = {"autopilot healthy": len(ah), "threshold healthy": len(th), "ask-first healthy": len(kh), "ask-first supported": len(ks),
            "autopilot supported": len(As), "autopilot cpu_burn": len(cb)}
    out = []

    def add(n, text, ok, complete, detail):
        out.append({"n": n, "criterion": text, "verdict": verdict(ok, complete), "detail": detail})

    # 1 ask-first never blocked
    ask_all = kh + ks
    fails = sum(((r.get("approver") or {}).get("approve_failures") or 0) for r in ask_all)
    terr = sum(((r.get("approver") or {}).get("thread_errors") or 0) for r in ask_all)
    no_approver = sum(1 for r in ask_all if r.get("approver") is None)
    det = sum(1 for r in ks if sc(r, "detected"))
    rec = sum(1 for r in ks if sc(r, "recovered"))
    ok1 = fails == 0 and terr == 0 and no_approver == 0 and det == len(ks) and rec >= MIN_RECOVERED
    add(1, "ask-first: approve_failures == 0, thread_errors == 0, all 18 supported detected, >= 15/18 recovered", ok1,
        len(ks) == 18 and len(kh) == 8,
        f"runs {len(ask_all)}; approve_failures {fails}; thread_errors {terr}; rows without approver stats {no_approver}; detected {det}/{len(ks)}; recovered {rec}/{len(ks)}")
    # 2 incidents on healthy runs
    n_a = sum(1 for r in ah if (sc(r, "incidents_opened") or 0) > 0)
    th_by_seed = {r["seed"]: (sc(r, "incidents_opened") or 0) > 0 for r in th}
    n_t = sum(1 for r in ah if th_by_seed.get(r["seed"]))
    n_t_all = sum(th_by_seed.values())
    add(2, "autopilot healthy: <= 2/24 runs open an incident and no more than threshold_restart on the same seeds",
        n_a <= MAX_HEALTHY_INCIDENTS and n_a <= n_t_all, len(ah) == 24 and len(th) == 24,
        f"autopilot {n_a}/{len(ah)}; threshold_restart {n_t_all}/{len(th)} (on autopilot's incident seeds: {n_t})")
    # 3 actions on healthy runs
    act_a = sum(1 for r in ah if (sc(r, "actions_executed") or 0) > 0)
    act_k = sum(1 for r in kh if (sc(r, "actions_executed") or 0) > 0)
    add(3, "0 executed actions in the 24 autopilot and 8 ask-first healthy runs", act_a == 0 and act_k == 0, len(ah) == 24 and len(kh) == 8,
        f"autopilot runs with an action {act_a}/{len(ah)}; ask-first {act_k}/{len(kh)}")
    # 4 detection
    dts = [sc(r, "time_to_detect_s") for r in As if sc(r, "detected") and sc(r, "time_to_detect_s") is not None]
    mean_d = sum(dts) / len(dts) if dts else float("nan")
    ndet = sum(1 for r in As if sc(r, "detected"))
    add(4, "autopilot supported: all 18 detected and mean detection <= 15.1 s", ndet == len(As) and bool(dts) and mean_d <= MAX_DETECT_S, len(As) == 18,
        f"detected {ndet}/{len(As)}; mean detection {mean_d:.2f} s")
    # 5 recovery
    recd = sum(1 for r in As if sc(r, "recovered"))
    cells = {}
    for s in SUPPORTED:
        xs = [r for r in As if r["scenario"] == s]
        cells[s] = (sum(1 for r in xs if sc(r, "recovered")), len(xs))
    bad_cells = [s for s, (k, n) in cells.items() if k < CELL_MIN.get(s, 2)]
    add(5, "autopilot supported: >= 15/18 recovered, no cell below 2/3 (crash 1/3)", recd >= MIN_RECOVERED and not bad_cells, len(As) == 18,
        f"recovered {recd}/{len(As)}; cells " + ", ".join(f"{s} {k}/{n}" for s, (k, n) in cells.items()) + (f"; below minimum: {bad_cells}" if bad_cells else ""))
    # 6 failed-request %
    fp = [sc(r, "failed_request_pct") for r in As if sc(r, "failed_request_pct") is not None]
    mf = sum(fp) / len(fp) if fp else float("nan")
    add(6, "autopilot supported: pooled mean failed-request % <= 23.4", bool(fp) and mf <= MAX_FAILED_PCT, len(As) == 18 and len(fp) == 18,
        f"mean {mf:.2f}% over {len(fp)} runs")
    # 7 unseen fault
    ab = sum(1 for r in cb if sc(r, "abstained_correctly"))
    add(7, "cpu_burn: abstained correctly in >= 2 of 3", ab >= MIN_ABSTAIN, len(cb) == 3, f"abstained {ab}/{len(cb)}")
    allpass = all(o["verdict"] == "PASS" for o in out)
    return out, have, allpass


def render(out, have, allpass):
    L = ["# v2 pass criteria (applied mechanically; Amendment 4 section N, demo rule P)", "",
         "Run counts found vs the plan: " + "; ".join(f"{k} {have[k]}/{v}" for k, v in EXPECTED.items()), "",
         "| # | criterion | verdict | counts |", "|---|---|---|---|"]
    L += [f"| {o['n']} | {o['criterion']} | **{o['verdict']}** | {o['detail']} |" for o in out]
    if allpass:
        dec = "all criteria PASS: per rule P the demo may show v2."
    elif any(o["verdict"] == "INCOMPLETE" for o in out):
        dec = "not decidable yet (INCOMPLETE criteria): the demo stays on v1 until the runs are complete."
    else:
        dec = "at least one criterion FAILS: per rule P the demo uses v1 with its issues stated plainly. Failed criteria are reported as failed."
    return "\n".join(L + ["", f"**Demo decision (rule P):** {dec}", ""])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", required=True)
    ap.add_argument("--out")
    a = ap.parse_args()
    text = render(*evaluate(load(a.raw)))
    if a.out:
        Path(a.out).write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
