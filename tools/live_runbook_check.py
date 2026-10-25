"""Smoke test: exercise each runbook against the running compose stack and verify checkout.

Requires `docker compose up -d`. Uses the same chaos hook the evaluator uses, via exec.
    python tools/live_runbook_check.py
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine.executor import ExecutionError, Executor  # noqa: E402
from engine.verify import verify_recovery  # noqa: E402

ex = Executor()


def chaos(svc, body):
    code = ("import urllib.request,json;"
            "r=urllib.request.Request('http://localhost:8000/_chaos',data=json.dumps(%s).encode(),"
            "headers={'Content-Type':'application/json'});print(urllib.request.urlopen(r).read())"
            % json.dumps({**body, "token": "evaluator-only"}))
    return ex._container(svc).exec_run(["python", "-c", code])[1].decode().strip()


def scratch(svc):
    return ex._container(svc).exec_run(["du", "-sk", "/tmp/eai-scratch"])[1].decode().strip()


print("restart:", ex.run("restart_service", "inventory", "smoke"))
time.sleep(4)
print(" verify:", verify_recovery(8))
print("disk fill:", chaos("payments", {"kind": "disk", "value": 20}), "| before:", scratch("payments"))
print("clear:", ex.run("clear_temp_path", "payments", "smoke"), "| after:", scratch("payments"))
print("recreate:", ex.run("recreate_container", "orders", "smoke"))
time.sleep(4)
print(" verify:", verify_recovery(10))
try:
    ex.run("rollback_release", "web", "smoke")
except ExecutionError as e:
    print("rollback without an earlier image is refused:", e)
