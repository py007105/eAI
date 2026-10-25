"""Assign a triage class (a harness artifact / b system bug / c design limitation) to every non-recovery, by explicit rules, from the recorded rows.

    python tools/triage_nonrecoveries.py --raw results/benchmark-v1/benchmark_raw.jsonl --out-json docs/postmortems/triage.json --out-md docs/postmortems/benchmark-v1-triage.md

Rules (docs/EVALUATION_PLAN.md section 9), applied in this order to each supported-fault run with recovered != True, arm != no_action:
 R1 (eternalai_ask_first) a proposal was left awaiting approval and never approved, and this run is that run or a later one in the arm  -> (a) harness artifact (the approval token never worked), amplified by (b) a pending approval that never expires
 R2 (eternalai) the first incident abstained and the target is `orders` with scenario `crash`                                           -> (c) thin coverage
 R3 any arm: a policy-blocked action whose reason is a cooldown from an earlier run                                                    -> (a) brain state carried across runs
 R4 any arm: final status executing / verifying / open (an action or incident was still in flight when the run window ended)           -> (a) run ended in flight
 R5 any arm: final status undetected (no incident ever opened)                                                                          -> (c) detection limit of that arm's rule
 R6 otherwise (escalated / unresolved / partially recovered after the arm's own action or abstention)                                    -> (c) design limitation, with the facts listed
The facts used are written next to each class; a human reads the table, and any run whose evidence contradicts its rule must be reclassified by hand in
docs/postmortems/. The rules are explicit so a reader can disagree with them, and they are not tuned to any metric.
"""
import argparse
import json
from collections import Counter
from pathlib import Path

SUPPORTED = ["crash", "latency", "error_spike", "memory_leak", "disk_fill", "bad_deploy"]


def facts(r):
    inc = r.get("incidents") or []
    acts = [f"{a['runbook_id']}@{a['service']}:{a['verdict']}" for i in inc for a in i.get("actions") or []]
    return {"final": r["score"].get("final_status"), "incidents": [(i["status"], i["likely_cause"], bool(i["abstained"])) for i in inc], "actions": acts}


def blocked_by_cooldown(r):
    return any(a["verdict"] == "blocked" and str(a.get("reason", "")).startswith("cooldown") for i in r.get("incidents") or [] for a in i.get("actions") or [])


def classify(rows):
    out = []
    ask = sorted([r for r in rows if r["arm"] == "eternalai_ask_first"], key=lambda r: r["finished_at"])
    stuck_from = next((r["finished_at"] for r in ask if any(i["status"] == "awaiting_approval" and not any(a.get("approved_by") for a in i["actions"])
                                                           for i in r.get("incidents") or [])), None)
    for r in rows:
        s = r["score"]
        if r["arm"] == "no_action" or r["scenario"] not in SUPPORTED or s.get("recovered") is True:
            continue
        f, inc = facts(r), r.get("incidents") or []
        if r["arm"] == "eternalai_ask_first" and stuck_from and r["finished_at"] >= stuck_from:
            cls, why = "a", ("R1 harness artifact: an ask-first proposal stayed awaiting_approval because the harness token was refused by the brain (HTTP 503, placeholder token); amplifier (b): no expiry, so it blocked every later detection in the arm"
                             if f["final"] != "undetected" else "R1 harness artifact: undetected because an earlier proposal stayed awaiting_approval (the harness token was refused by the brain) and, with no expiry (b), blocked new incidents")
        elif r["arm"].startswith("eternalai") and r["scenario"] == "crash" and r["target"] == "orders" and inc and inc[0]["abstained"]:
            cls, why = "c", "R2 first incident abstained (insufficient_evidence) on a crash of orders; orders has 1 crash run in training"
        elif blocked_by_cooldown(r):
            cls, why = "a", "R3 restart blocked by a cooldown left by an action in an earlier run (the brain is not reset between runs)"
        elif f["final"] in ("executing", "verifying", "open"):
            cls, why = "a", f"R4 the run window ended while the incident was still '{f['final']}'"
        elif f["final"] == "undetected":
            cls, why = "c", "R5 no incident was ever opened by this arm's detector"
        else:
            cls, why = "c", "R6 the arm acted or escalated and the fault was not reported recovered"
        out.append({"arm": r["arm"], "scenario": r["scenario"], "seed": r["seed"], "class": cls,
                    "evidence": f"{why}; final={f['final']}; actions={f['actions']}; incidents={f['incidents']}"})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", required=True)
    ap.add_argument("--out-json", required=True)
    ap.add_argument("--out-md", required=True)
    a = ap.parse_args()
    rows = [json.loads(line) for line in Path(a.raw).read_text().splitlines()]
    res = classify(rows)
    Path(a.out_json).write_text(json.dumps(res, indent=1), encoding="utf-8")
    cnt = Counter((x["arm"], x["class"]) for x in res)
    md = ["# Benchmark v1: triage of every non-recovery (rule-based; see `tools/triage_nonrecoveries.py`)\n",
          f"{len(res)} non-recoveries on supported faults (arms other than no_action). Counts by arm and class:\n",
          "| arm | a harness artifact | b system bug | c design limitation |\n|---|---|---|---|"]
    for arm in sorted({x["arm"] for x in res}):
        md.append(f"| {arm} | {cnt[(arm, 'a')]} | {cnt[(arm, 'b')]} | {cnt[(arm, 'c')]} |")
    md += ["", "Every run, with its facts:\n", "| arm | scenario | seed | class | evidence |", "|---|---|---|---|---|"]
    md += [f"| {x['arm']} | {x['scenario']} | {x['seed']} | {x['class']} | {x['evidence']} |" for x in sorted(res, key=lambda x: (x["arm"], x["scenario"], x["seed"]))]
    Path(a.out_md).write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"{len(res)} classified; counts: {dict(cnt)}")


if __name__ == "__main__":
    main()
