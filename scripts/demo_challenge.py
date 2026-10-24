"""Demo helper (tooling only; no system code): start a hidden challenge from a restricted list, and reveal it later.

    python scripts/demo_challenge.py start            # hidden pick among the 6 supported faults and the 2 healthy scenarios (never cpu_burn)
    python scripts/demo_challenge.py start --unseen   # the clearly labelled unseen-fault segment (cpu_burn); run it in ask-first mode
    python scripts/demo_challenge.py status RUN_ID
    python scripts/demo_challenge.py reveal RUN_ID    # truth and score; the evaluator refuses until the run is scored

WHY: the dashboard's "Start blind challenge" button posts with no scenario, and the evaluator then draws from all 9 scenarios including the unseen fault
(`evaluator/main.py`: `rng.choice(list(SCENARIOS))`). Changing that would be a system change, so the live challenge is started from here instead. The scenario is drawn
with `secrets` and is NOT printed, so the presenter does not know it; the evaluator keeps the truth until the run is scored. The dashboard shows incidents,
approvals and the service map for any run; its own reveal button only works for runs it started, so the reveal is done here.
"""
import argparse
import getpass
import json
import os
import secrets
import sys

import httpx

EVALUATOR = "http://localhost:8200"
POOL = ["crash", "latency", "error_spike", "memory_leak", "disk_fill", "bad_deploy", "traffic_surge", "good_deploy"]
UNSEEN = "cpu_burn"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["start", "status", "reveal"])
    ap.add_argument("run_id", nargs="?")
    ap.add_argument("--unseen", action="store_true")
    ap.add_argument("--base", default=EVALUATOR)
    a = ap.parse_args()
    if a.cmd == "start":
        # Starting a run injects a real fault, so the evaluator requires the approval token. Taken from the environment or typed
        # at a hidden prompt; never printed.
        token = os.getenv("ETERNALAI_APPROVAL_TOKEN") or getpass.getpass("approval token (hidden): ")
        scen = UNSEEN if a.unseen else secrets.choice(POOL)
        r = httpx.post(f"{a.base}/runs", json={"scenario": scen}, timeout=15, headers={"X-Approval-Token": token.strip()})
        if r.status_code in (403, 503):
            sys.exit(f"{r.status_code}: the evaluator refused the approval token")
        r.raise_for_status()
        out = {"run_id": r.json()["run_id"], "segment": "UNSEEN FAULT (labelled)" if a.unseen else "hidden pick from supported faults and healthy runs"}
        print(json.dumps(out))
        return 0
    if not a.run_id:
        sys.exit("run_id required")
    r = httpx.get(f"{a.base}/runs/{a.run_id}/{'status' if a.cmd == 'status' else 'reveal'}", timeout=15)
    print(json.dumps(r.json(), indent=1) if r.status_code == 200 else f"{r.status_code}: {r.text}")
    return 0 if r.status_code == 200 else 1


if __name__ == "__main__":
    sys.exit(main())
