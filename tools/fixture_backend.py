"""Fixture backend for dashboard design review. NOT real telemetry: hand-made sample data.

    FIXTURE=recovered|awaiting|down|abstained python tools/fixture_backend.py   # serves on :8001

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
    "abstained": {"web": svc(True), "orders": svc(True), "inventory": svc(True), "payments": svc()},
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
                           "likely_cause": "down", "runbook_id": None, "missing_information": ["restart did not restore checkout"]}},
       "abstained": {**BASE, "status": "escalated", "kind": "reactive", "likely_cause": "insufficient_evidence", "abstained": True, "confidence": 0.9999,
                     "forecasts": [], "actions": [], "ranking": [{"service": "inventory", "score": 0.97}, {"service": "orders", "score": 0.02},
                                                                  {"service": "web", "score": 0.01}, {"service": "payments", "score": 0.0}],
                     "report": {**BASE["report"], "summary": "Anomaly on inventory does not match a known fault pattern with enough confidence, so no automatic action "
                                "is proposed. Evidence is preserved for a human.", "likely_cause": "insufficient_evidence", "runbook_id": None,
                                "missing_information": ["fault pattern not seen in training", "human review needed"]},
                     "report_meta": {"provider": "gemini", "llm_disagreed": True}}}[STATE]

app = FastAPI()


@app.get("/status")
def status():
    return {"mode": "ask-first", "models": {"detectors": True, "classifier": True, "ranker": True, "baselines": True},
            "model_meta": {}, "fallbacks_in_use": [], "breakers_open": ["inventory"] if STATE == "down" else [],
            "last_error": None, "open_incidents": 0 if STATE == "recovered" else 1,
            **({"calibration": {"show_probability": True}} if STATE == "abstained" else {})}


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
    return {"runs": 10 + SCORED["n"], "by_scenario": {"memory_leak (fixture)": row(1), "bad_deploy (fixture)": row(2, recovered=4)}}


# --- evaluator endpoints for Demo mode screenshots (same app; point EVALUATOR_URL here). A run is "running" for RUN_S seconds,
# scored (scorecard +1, still "running" = restoring) for 4 more, then "finished". Hand-made outcomes, not telemetry.
RUN_S = float(os.getenv("FIXTURE_RUN_S", "8"))
EV_RUNS = {}
SCORED = {"n": 0}
OUTCOMES = {"cpu_burn": ("inventory", {"detected": True, "abstained_correctly": True, "actions_executed": 0, "incidents_opened": 1, "recovered": False,
                                        "failed_request_pct": 0.0, "final_status": "escalated"})}
DEFAULT_OUTCOME = ("orders", {"detected": True, "recovered": True, "time_to_verified_recovery_s": 41.6, "failed_request_pct": 10.81,
                              "incidents_opened": 1, "actions_executed": 1, "final_status": "recovered"})


@app.post("/runs")
def ev_start(req: dict):
    rid = f"fx{len(EV_RUNS) + 1:04d}"
    EV_RUNS[rid] = {"t": time.time(), "scenario": req.get("scenario") or "crash", "scored": False}
    return {"run_id": rid, "blind": req.get("scenario") is None}


@app.get("/runs/{rid}/status")
def ev_status(rid: str):
    r = EV_RUNS[rid]
    el = time.time() - r["t"]
    if el >= RUN_S and not r["scored"]:
        r["scored"] = True
        SCORED["n"] += 1
    return {"run_id": rid, "state": "finished" if el >= RUN_S + 4 else "running", "elapsed_s": round(el, 1)}


@app.get("/runs/{rid}/reveal")
def ev_reveal(rid: str):
    r = EV_RUNS[rid]
    tgt, sc = OUTCOMES.get(r["scenario"], DEFAULT_OUTCOME)
    if r["scenario"] in ("traffic_surge", "good_deploy"):
        tgt, sc = "web", {"detected": False, "incidents_opened": 0, "actions_executed": 0, "failed_request_pct": 0.0}
    return {"truth": {"run_id": rid, "scenario": r["scenario"], "target": tgt}, "score": {"run_id": rid, **sc}}


@app.post("/challenge/start")
def start():
    return {"run_id": "fixture1"}


@app.get("/challenge/{rid}/status")
def cstatus(rid: str):
    return {"state": "running", "elapsed_s": 37.0}


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=int(os.getenv("FIXTURE_PORT", "8001")), log_level="warning")
