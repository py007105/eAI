"""Smoke test the evaluator: blind run hides truth until finished, then reveal and restore.

    python scripts/evaluator_smoke.py [scenario] [target]   (EternalAI need not be running)
"""
import sys
import time

import httpx

EV = "http://localhost:8200"
body = {"timeout_s": 25, "healthy_s": 20}
if len(sys.argv) > 1:
    body["scenario"] = sys.argv[1]
if len(sys.argv) > 2:
    body["target"] = sys.argv[2]
r = httpx.post(f"{EV}/runs", json=body, timeout=10).json()
print("started:", r)
rid = r["run_id"]
time.sleep(3)
print("status while running:", httpx.get(f"{EV}/runs/{rid}/status").json())
print("reveal while running ->", httpx.get(f"{EV}/runs/{rid}/reveal").status_code, "(409 expected)")
while httpx.get(f"{EV}/runs/{rid}/status").json()["state"] == "running":
    time.sleep(3)
print("final status:", httpx.get(f"{EV}/runs/{rid}/status").json())
print("reveal:", httpx.get(f"{EV}/runs/{rid}/reveal").json())
