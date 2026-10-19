"""Read-only: on the evaluated v2 fault runs, how many opened more than one incident or executed more than one action for the same injected fault?

    python scripts/multi_incident_check.py [--evaluated results/benchmark-v2/rerun/benchmark_v2_evaluated.jsonl] [--out docs/results/multi_incident.md]

Counts come from each row's score (incidents_opened, actions_executed) and its recorded incident list; nothing is edited.
"""
import argparse
import json
from collections import defaultdict
from pathlib import Path

SUPPORTED = ["crash", "latency", "error_spike", "memory_leak", "disk_fill", "bad_deploy"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--evaluated", default="results/benchmark-v2/rerun/benchmark_v2_evaluated.jsonl")
    ap.add_argument("--out", default="docs/results/multi_incident.md")
    a = ap.parse_args()
    rows = [json.loads(x) for x in Path(a.evaluated).read_text(encoding="utf-8").splitlines() if x.strip()]
    rows = [r for r in rows if r["scenario"] in SUPPORTED and r["arm"] in ("eternalai_autopilot", "eternalai_ask_first")]
    by = defaultdict(lambda: defaultdict(list))
    for r in rows:
        by[r["arm"]][r["scenario"]].append(r)
    L = ["# Multiple incidents or actions for one fault (evaluated v2 supported-fault runs, script output)", "",
         f"Rows examined: {len(rows)} (autopilot and ask-first, six supported fault types). 'More than one incident' = `incidents_opened` > 1; 'more than one action' = `actions_executed` > 1.", "",
         "| arm | scenario | runs | runs with >1 incident | runs with >1 executed action | seeds affected | runbooks executed in affected runs |", "|---|---|---|---|---|---|---|"]
    tot = {"inc": 0, "act": 0}
    for arm in ("eternalai_autopilot", "eternalai_ask_first"):
        for sc in SUPPORTED:
            rs = by[arm][sc]
            mi = [r for r in rs if (r["score"].get("incidents_opened") or 0) > 1]
            ma = [r for r in rs if (r["score"].get("actions_executed") or 0) > 1]
            tot["inc"] += len(mi)
            tot["act"] += len(ma)
            aff = sorted({r["seed"] for r in mi + ma})
            rb = sorted({f"{x['runbook_id']}@{x['service']}" for r in mi + ma for i in r["incidents"] for x in (i.get("actions") or []) if x.get("executed")})
            L.append(f"| {arm} | {sc} | {len(rs)} | {len(mi)} | {len(ma)} | {' '.join(map(str, aff)) or '-'} | {', '.join(rb) or '-'} |")
    L += ["", f"Total: {tot['inc']} runs with more than one incident and {tot['act']} runs with more than one executed action, of {len(rows)} fault runs."]
    Path(a.out).write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
