"""Fixture backend for dashboard design review. NOT real telemetry: hand-made sample data.

    FIXTURE=recovered|awaiting|down python scripts/fixture_backend.py   # serves on :8001

Serves the same endpoints the dashboard uses so the populated UI can be screenshotted without Docker.
"""
import os
import time

import uvicorn
from fastapi import FastAPI

STATE = os.getenv("FIXTURE", "recovered")
now = time.time()
TOPO = {"web": ["orders", "inventory"], "orders": ["inventory", "payments"], "inventory": [], "payments": []}


def svc(anom=False, up=True, running=True):
    return {"features": {"lat_ratio": 4.2 if anom else 1.0, "error_ratio": 0.38 if anom else 0.0, "up_frac": 1.0 if up else 0.0,
                         "mem_share": 0.71 if anom else 0.26},
            "score": 0.71 if anom else 0.41, "anomalous": anom, "state": {"running": running, "image_tag": "v1"}}


SERVICES = {
    "recovered": {"web": svc(), "orders": svc(), "inventory": svc(), "payments": svc()},
    "awaiting": {"web": svc(True), "orders": svc(True), "inventory": svc(True), "payments": svc()},
    "down": {"web": svc(True), "orders": svc(True), "inventory": svc(True, up=False, running=False), "payments": svc()},
}[STATE]

TIMELINE = [{"t": now - 60 + dt, "msg": m} for dt, m in [
    (0, "anomaly confirmed on ['inventory', 'orders']"), (5, "diagnosed memory_leak on inventory (report by template)"),
    (5.2, "policy: needs_approval - ask-first: medium-risk action requires approval")]]
EVIDENCE = [
    {"id": "ev1", "tool": "metrics", "service": "inventory", "summary": "inventory window metrics: lat_ratio=4.2, error_ratio=0.38, mem_share=0.71"},
    {"id": "ev2", "tool": "container", "service": "inventory", "summary": "inventory container running, image tag v1, exit_code=0, oom_killed=False"},
    {"id": "ev3", "tool": "forecast", "service": "inventory", "summary": "inventory memory rising 118.0 MB/min, 71% of limit; exhaustion in 38-61s"},
    {"id": "ev4", "tool": "dependency_failures", "service": None, "summary": "failing calls (per second): {'orders->inventory': 2.4}"}]
FORECAST = {"resource": "memory", "slope_per_min": 118e6, "share_of_limit_now": 0.71, "eta_s": 49, "eta_earliest_s": 38,
            "eta_latest_s": 61, "confidence": 0.9, "points": 40, "steady_fraction": 1.0}
BASE = {"id": "a1b2c3d4", "opened_t": now - 60, "closed_t": None, "kind": "predicted", "services": ["inventory", "orders"],
        "ranking": [{"service": "inventory", "score": 0.74}, {"service": "orders", "score": 0.19}, {"service": "web", "score": 0.05},
                    {"service": "payments", "score": 0.02}],
        "likely_cause": "memory_leak", "confidence": 0.93, "abstained": False,
        "report": {"summary": "inventory shows signs of memory leak (classifier confidence 0.93). Proposed runbook: recreate_container. "
                              "Recovery is only confirmed after the synthetic checkout passes.", "evidence_ids": ["ev1", "ev3"],
                   "likely_cause": "memory_leak", "alternative_causes": ["bad_deploy"], "runbook_id": "recreate_container",
                   "missing_information": []},
        "report_meta": {"provider": "template", "llm_disagreed": False}, "timeline": TIMELINE, "evidence": EVIDENCE,
        "forecasts": [FORECAST], "before": {"checkout_success": 0.0, "error_ratio": 0.41, "p95_s": 1.38}, "after": None,
        "verification": None, "actions": [{"t": now - 55, "runbook_id": "recreate_container", "service": "inventory",
                                           "verdict": "needs_approval", "executed": False, "risk": "medium",
                                           "reason": "ask-first: medium-risk action requires approval"}]}
INC = {"recovered": {**BASE, "status": "recovered", "closed_t": now - 5,
                     "timeline": TIMELINE + [{"t": now - 40, "msg": "executed recreate_container on inventory by human:dashboard"},
                                             {"t": now - 12, "msg": "verification: recovered (100% of 20 checkouts)"}],
                     "actions": [{**BASE["actions"][0], "executed": True, "verdict": "needs_approval"}],
                     "verification": {"outcome": "recovered", "success_rate": 1.0, "probes": 20, "p_max_latency_s": 0.094, "t": now - 5},
                     "after": {"checkout_success": 1.0, "error_ratio": 0.0, "p95_s": 0.052}},
       "awaiting": {**BASE, "status": "awaiting_approval"},
       "down": {**BASE, "status": "escalated", "kind": "reactive", "likely_cause": "down", "confidence": None, "forecasts": [],
                "report": {**BASE["report"], "summary": "inventory is down and no safe automatic action succeeded; evidence preserved for a human.",
                           "likely_cause": "down", "runbook_id": None, "missing_information": ["restart did not restore checkout"]}}}[STATE]

app = FastAPI()


@app.get("/status")
def status():
    return {"mode": "ask-first", "models": {"detectors": True, "classifier": True, "ranker": True, "baselines": True},
            "model_meta": {}, "fallbacks_in_use": [], "breakers_open": ["inventory"] if STATE == "down" else [],
            "last_error": None, "open_incidents": 0 if STATE == "recovered" else 1}


@app.get("/services")
def services():
    return {"services": SERVICES, "topology": TOPO, "depfail": {"orders->inventory": 2.4 if STATE != "recovered" else 0.0}}


@app.get("/incidents")
def incidents():
    return [INC]


@app.get("/approvals")
def approvals():
    if STATE != "awaiting":
        return []
    a = INC["actions"][0]
    return [{"incident_id": INC["id"], "service": a["service"], "runbook_id": a["runbook_id"], "risk": a["risk"],
             "reason": a["reason"], "cause": INC["likely_cause"], "report": INC["report"]}]


@app.get("/scorecard")
def scorecard():
    row = lambda n, **k: {"runs": 5, "detected": 5, "time_to_detect_s": {"mean": 9.4, "sd": 1.8, "n": 5},
                          "time_to_verified_recovery_s": {"mean": 41.0, "sd": 6.2, "n": 5},
                          "failed_request_pct": {"mean": 3.1, "sd": 1.2, "n": 5}, "top1": 5, "top3": 5, "recovered": 5,
                          "false_alerts": 0, "harmful_interventions": 0, **k}
    return {"runs": 10, "by_scenario": {"memory_leak (fixture)": row(1), "bad_deploy (fixture)": row(2, recovered=4)}}


@app.post("/challenge/start")
def start():
    return {"run_id": "fixture1"}


@app.get("/challenge/{rid}/status")
def cstatus(rid: str):
    return {"state": "running", "elapsed_s": 37.0}


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=int(os.getenv("FIXTURE_PORT", "8001")), log_level="warning")
