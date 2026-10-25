"""Per-cell table of the evaluated v2 set (read-only): planned / done / valid-original / re-run, and the outcome counts per cell. All numbers computed here.

    python tools/v2_cell_table.py --evaluated .../benchmark_v2_evaluated.jsonl --rerun .../benchmark_v2_rerun_raw.jsonl [--out docs/results/v2_cell_table.md]
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from benchmark_status import V2_PLAN  # noqa: E402

SC = ["crash", "latency", "error_spike", "memory_leak", "disk_fill", "bad_deploy", "cpu_burn", "traffic_surge", "good_deploy"]
ARMS = ["eternalai_autopilot", "threshold_restart", "eternalai_ask_first"]


def rows(p):
    return [json.loads(x) for x in Path(p).read_text(encoding="utf-8").splitlines() if x.strip()]


def table(ev, rerun):
    rk = {(r["arm"], r["scenario"], r["seed"]) for r in rerun}
    L = ["| arm | scenario | planned | done | INCOMPLETE | valid original | re-run | detected | recovered | mean failed % | incident opened | action executed | abstained correctly |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for (arm, sc), n in sorted(V2_PLAN.items(), key=lambda kv: (ARMS.index(kv[0][0]), SC.index(kv[0][1]))):
        rs = [r for r in ev if r["arm"] == arm and r["scenario"] == sc]
        re_ = [r for r in rs if (r["arm"], r["scenario"], r["seed"]) in rk]
        s = [r["score"] for r in rs]
        fp = [x["failed_request_pct"] for x in s if x.get("failed_request_pct") is not None]
        L.append(f"| {arm} | {sc} | {n} | {len(rs)} | {'INCOMPLETE' if len(rs) < n else '-'} | {len(rs) - len(re_)} | {len(re_)} | "
                 f"{sum(1 for x in s if x.get('detected'))}/{len(s)} | {sum(1 for x in s if x.get('recovered'))}/{len(s)} | "
                 f"{(sum(fp) / len(fp)) if fp else float('nan'):.2f} | {sum(1 for x in s if (x.get('incidents_opened') or 0) > 0)}/{len(s)} | "
                 f"{sum(1 for x in s if (x.get('actions_executed') or 0) > 0)}/{len(s)} | {sum(1 for x in s if x.get('abstained_correctly'))}/{len(s)} |")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--evaluated", required=True)
    ap.add_argument("--rerun", required=True)
    ap.add_argument("--out")
    a = ap.parse_args()
    t = "# v2 evaluated set, per cell (script output)\n\n" + table(rows(a.evaluated), rows(a.rerun)) + "\n"
    if a.out:
        Path(a.out).write_text(t, encoding="utf-8")
    print(t)


if __name__ == "__main__":
    main()
