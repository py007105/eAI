"""DIAGNOSTIC (post-mortem tooling, not a benchmark run): replay the benchmark's simulated operator with every HTTP status logged.

The benchmark approver (scripts/run_benchmark.py::approver) swallows errors and never checks the status of the approve call, so the cause of the
ask-first arm's missing approvals cannot be read from the v1 records. This script starts one evaluator run on a NON-benchmark seed with the brain in
ask-first mode (already running) and prints what GET /approvals and POST /approvals/<id>/approve return.

    python scripts/diag_approver.py --scenario bad_deploy --seed 2105 [--token benchmark-token-not-a-secret] [--after 5]
"""
import argparse
import time

import httpx

EV, EAI = "http://localhost:8200", "http://localhost:8000"

ap = argparse.ArgumentParser()
ap.add_argument("--scenario", default="bad_deploy")
ap.add_argument("--seed", type=int, required=True)
ap.add_argument("--token", default="benchmark-token-not-a-secret")
ap.add_argument("--after", type=float, default=5.0)
ap.add_argument("--timeout-s", type=int, default=90)
a = ap.parse_args()
assert a.seed >= 2000, "diagnostic runs must use non-benchmark seeds"

r = httpx.post(f"{EV}/runs", json={"scenario": a.scenario, "seed": a.seed, "timeout_s": a.timeout_s, "healthy_s": 60}, timeout=20)
rid = r.json()["run_id"]
print("run", rid, flush=True)
t_start, first_seen, last = time.time(), {}, None
while httpx.get(f"{EV}/runs/{rid}/status", timeout=10).json()["state"] == "running":
    try:
        resp = httpx.get(f"{EAI}/approvals", timeout=3)
        items = resp.json()
        if (len(items), resp.status_code) != last:
            print(f"+{time.time() - t_start:6.1f}s GET /approvals -> {resp.status_code}, {len(items)} pending", flush=True)
            last = (len(items), resp.status_code)
        for it in items:
            t0 = first_seen.setdefault(it["incident_id"], time.time())
            if time.time() - t0 >= a.after:
                p = httpx.post(f"{EAI}/approvals/{it['incident_id']}/approve", json={"approver": "benchmark-operator"},
                               headers={"X-Approval-Token": a.token}, timeout=5)
                print(f"+{time.time() - t_start:6.1f}s POST approve {it['incident_id']} ({it['runbook_id']} on {it['service']}) -> {p.status_code} {p.text[:200]}", flush=True)
    except Exception as e:  # noqa: BLE001 - the point is to see every failure
        print(f"+{time.time() - t_start:6.1f}s {type(e).__name__}: {e}", flush=True)
    time.sleep(1)
rev = httpx.get(f"{EV}/runs/{rid}/reveal", timeout=10).json()
print("score:", {k: rev["score"].get(k) for k in ("detected", "recovered", "final_status", "incidents_opened", "actions_executed")})
