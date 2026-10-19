"""Mark v2 rows invalid by the pre-registered timestamp rule (Amendment 8) and derive the re-run plan. Read-only on the raw file.

    python scripts/v2_validity_mark.py --raw D:/eAI/eAI-workspace/eAI/results/benchmark-v2/benchmark_v2_raw.jsonl
        [--rerun-raw PATH] [--out-json invalid_rows.json] [--out-md docs/results/v2_invalid_and_rerun_plan.md]

RULE (fixed before any row is classified; stock records, not outcomes):
  cutoff = the time of the last verification probe in the v2 file that completed a checkout (a confirmed order). The stock never rises, so sku-mug had stock until then.
  A row is INVALID if its run ends after the cutoff (score.t_end > cutoff). This covers a run that starts before and ends after the cutoff, and every run between the cutoff
  and the first HTTP 409 probe (treated as invalid, conservatively). Rows that look clean are not exempt: the rule is applied to every row.
RE-RUN PLAN: per (scenario, seed) group of arms (the paired design):
  - some arms of the group are valid and some invalid: re-run the invalid arms on the SAME seed;
  - every arm of the group is invalid: one FRESH seed for the whole group, seed = 400 + 10 * k + scenario index (k = 0, 1, ... per scenario).
Originals stay in the raw file; this script only writes the sidecar list.
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from benchmark_status import V2_PLAN  # noqa: E402

SCENARIOS = ["crash", "latency", "error_spike", "memory_leak", "disk_fill", "bad_deploy", "cpu_burn", "traffic_surge", "good_deploy"]
ARM_ORDER = ["eternalai_autopilot", "threshold_restart", "eternalai_ask_first"]
# the pre-registered run order (stage3_eval.PLAN), as (segment label, arm, scenarios)
SEGMENTS = [("P1", "eternalai_autopilot", ["traffic_surge", "good_deploy"]), ("P1", "threshold_restart", ["traffic_surge", "good_deploy"]),
            ("P1/P2", "eternalai_ask_first", ["traffic_surge", "good_deploy"]),
            ("P2", "eternalai_ask_first", ["crash", "latency", "error_spike", "memory_leak", "disk_fill", "bad_deploy"]),
            ("P3", "eternalai_autopilot", ["crash", "latency", "error_spike", "memory_leak", "disk_fill", "bad_deploy", "cpu_burn"])]
FRESH_SEED0 = 400


def ist(ts):
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))


def load(path):
    d = {}
    for x in Path(path).read_text(encoding="utf-8").splitlines():
        if x.strip():
            r = json.loads(x)
            d[(r["arm"], r["scenario"], r["seed"])] = r
    return d


def cutoff_time(rows):
    """Time of the last probe that completed a checkout, and of the first probe that got HTTP 409."""
    ok, bad = [], []
    for r in rows.values():
        for i in r.get("incidents") or []:
            v = i.get("verification")
            if not v:
                continue
            if (v.get("success_rate") or 0) > 0:
                ok.append(v["t"])
            if "409" in str(v.get("last_detail")):
                bad.append(v["t"])
    return (max(ok) if ok else None), (min(bad) if bad else None)


def classify(rows, cutoff):
    return {k: r["score"]["t_end"] > cutoff for k, r in rows.items()}      # True = invalid


def plan(rows, invalid):
    """Return (cells, jobs). jobs: [{segment, arm, scenario, seed, kind, group}] in the pre-registered run order."""
    groups = {}
    for (arm, scen, seed) in rows:
        groups.setdefault((scen, seed), {})[arm] = invalid[(arm, scen, seed)]
    fresh_k, jobs, mapped = {}, [], {}
    for (scen, seed), arms in sorted(groups.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        if all(arms.values()):
            k = fresh_k.get(scen, 0)
            fresh_k[scen] = k + 1
            new = FRESH_SEED0 + 10 * k + SCENARIOS.index(scen)
            for arm in arms:
                mapped[(arm, scen, seed)] = (new, "fresh")
        else:
            for arm, bad in arms.items():
                if bad:
                    mapped[(arm, scen, seed)] = (seed, "same-seed")
    for seg, arm, scens in SEGMENTS:
        todo = [(m[0], scen, m[1], k[2]) for k, m in mapped.items() if k[0] == arm and k[1] in scens for scen in [k[1]]]
        for seed, scen, kind, orig in sorted(todo):
            jobs.append({"segment": seg, "arm": arm, "scenario": scen, "seed": seed, "kind": kind, "replaces_seed": orig})
    cells = []
    for (arm, scen), n in sorted(V2_PLAN.items(), key=lambda kv: (ARM_ORDER.index(kv[0][0]), SCENARIOS.index(kv[0][1]))):
        have = [k for k in rows if k[0] == arm and k[1] == scen]
        bad = sum(invalid[k] for k in have)
        cells.append({"arm": arm, "scenario": scen, "planned": n, "found": len(have), "valid": len(have) - bad, "invalid": bad,
                      "rerun": sum(1 for j in jobs if j["arm"] == arm and j["scenario"] == scen)})
    return cells, jobs


def render(rows, invalid, cutoff, first409, cells, jobs):
    L = ["# v2 row validity and re-run plan (script output; Amendment 8)", "",
         f"- last probe that completed a checkout (cutoff): {ist(cutoff)} IST (epoch {cutoff:.3f})",
         f"- first probe answered HTTP 409: {ist(first409)} IST" if first409 else "- no probe answered 409",
         f"- rows in the raw file: {len(rows)}; invalid by the rule (run end after the cutoff): {sum(invalid.values())}; valid: {len(rows) - sum(invalid.values())}", "",
         "## Invalid rows (every one is listed; the originals stay in the file)", "", "| arm | scenario | seed | run end (IST) | seconds after cutoff | recovered | verification |", "|---|---|---|---|---|---|---|"]
    for k, r in sorted(rows.items(), key=lambda kv: kv[1]["score"]["t_end"]):
        if invalid[k]:
            vd = "; ".join(str((i.get("verification") or {}).get("last_detail")) for i in r.get("incidents") or []) or "none"
            L.append(f"| {k[0]} | {k[1]} | {k[2]} | {ist(r['score']['t_end'])} | {r['score']['t_end'] - cutoff:.1f} | {r['score'].get('recovered')} | {vd} |")
    L += ["", "## Valid rows that finish closest before the cutoff", "", "| arm | scenario | seed | run end (IST) | seconds before cutoff |", "|---|---|---|---|---|"]
    closest = [(k, r) for k, r in sorted(rows.items(), key=lambda kv: -kv[1]["score"]["t_end"]) if not invalid[k]][:5]
    L += [f"| {k[0]} | {k[1]} | {k[2]} | {ist(r['score']['t_end'])} | {cutoff - r['score']['t_end']:.1f} |" for k, r in closest]
    L +=["", "## Cell by cell (planned / found / valid / invalid / re-run)", "", "| arm | scenario | planned | found | valid | invalid | re-run |", "|---|---|---|---|---|---|---|"]
    L += [f"| {c['arm']} | {c['scenario']} | {c['planned']} | {c['found']} | {c['valid']} | {c['invalid']} | {c['rerun']} |" for c in cells]
    L += [f"| **total** | | {sum(c['planned'] for c in cells)} | {sum(c['found'] for c in cells)} | {sum(c['valid'] for c in cells)} | {sum(c['invalid'] for c in cells)} | {sum(c['rerun'] for c in cells)} |",
          "", "## Re-run jobs in the pre-registered order", "", "| # | segment | arm | scenario | seed | kind | replaces seed |", "|---|---|---|---|---|---|---|"]
    L += [f"| {n} | {j['segment']} | {j['arm']} | {j['scenario']} | {j['seed']} | {j['kind']} | {j['replaces_seed']} |" for n, j in enumerate(jobs, 1)]
    L += ["", f"Total re-run jobs: {len(jobs)}; same-seed {sum(1 for j in jobs if j['kind'] == 'same-seed')}; fresh-seed {sum(1 for j in jobs if j['kind'] == 'fresh')}", ""]
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", required=True)
    ap.add_argument("--out-json")
    ap.add_argument("--out-md")
    a = ap.parse_args()
    rows = load(a.raw)
    cutoff, first409 = cutoff_time(rows)
    if cutoff is None:
        sys.exit("no completed checkout probe found: cannot define the cutoff")
    invalid = classify(rows, cutoff)
    cells, jobs = plan(rows, invalid)
    text = render(rows, invalid, cutoff, first409, cells, jobs)
    if a.out_json:
        Path(a.out_json).write_text(json.dumps({
            "rule": "invalid if score.t_end > cutoff; cutoff = time of the last probe that completed a checkout (Amendment 8)",
            "cutoff_t": cutoff, "cutoff_ist": ist(cutoff), "first_409_t": first409,
            "invalid": [{"arm": k[0], "scenario": k[1], "seed": k[2], "t_end": rows[k]["score"]["t_end"], "finished_at": rows[k]["finished_at"],
                         "class": "a (harness/environment artifact: inventory stock exhausted)"} for k in sorted(rows) if invalid[k]],
            "jobs": jobs, "cells": cells}, indent=1), encoding="utf-8")
    if a.out_md:
        Path(a.out_md).write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
