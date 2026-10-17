"""EternalAI backend REST API (FastAPI). The dashboard talks only to this.

    uvicorn eternalai.api:app --port 8000

Approve / reject / mode changes need the X-Approval-Token header. The token has no default that
works: if ETERNALAI_APPROVAL_TOKEN is unset or left as the placeholder, those endpoints are refused.
"""
from __future__ import annotations

import hmac
import os
import threading
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

from . import config
from .engine import Engine

EVALUATOR_URL = os.getenv("EVALUATOR_URL", "http://localhost:8200")
engine: Engine | None = None


def make_engine() -> Engine:
    """ETERNALAI_BRAIN selects the brain: `eternalai` (default) or one of the benchmark baselines."""
    brain = os.getenv("ETERNALAI_BRAIN", "eternalai")
    if brain == "eternalai":
        return Engine()
    from .baselines import PrototypeRulesEngine, ThresholdRestartEngine
    cls = {"threshold_restart": ThresholdRestartEngine, "prototype_rules": PrototypeRulesEngine}.get(brain)
    if cls is None:
        raise RuntimeError(f"unknown ETERNALAI_BRAIN={brain!r}")
    return cls("autopilot")  # baselines have no approval flow


@asynccontextmanager
async def lifespan(app: FastAPI):
    global engine
    engine = make_engine()
    t = threading.Thread(target=engine.run_forever, daemon=True)
    t.start()
    yield
    engine.stop()


app = FastAPI(title="EternalAI", lifespan=lifespan)


def _auth(token: str | None):
    good = os.getenv("ETERNALAI_APPROVAL_TOKEN", "")
    if not good or good == "change-me":
        raise HTTPException(503, "approval API disabled: set ETERNALAI_APPROVAL_TOKEN to a real secret")
    if not token or not hmac.compare_digest(token, good):
        raise HTTPException(403, "invalid approval token")


class Who(BaseModel):
    approver: str = "operator"


class Mode(BaseModel):
    mode: str


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/status")
def status():
    return {"mode": engine.policy.mode, "brain": os.getenv("ETERNALAI_BRAIN", "eternalai"), "models": engine.models_loaded,
            "model_meta": {k: v and {"trained_at": v["trained_at_utc"], "git_commit": v["git_commit"]}
                           for k, v in (("detectors", engine.det_meta), ("classifier", engine.cls_meta),
                                        ("ranker", engine.rank_meta))},
            "fallbacks_in_use": [k for k, v in engine.models_loaded.items() if not v],
            # a probability may be shown as a percentage only if training verified its calibration (ECE <= 0.05)
            "calibration": {"ece": (engine.cls_meta or {}).get("ece_oof"),
                            "show_probability": bool((engine.cls_meta or {}).get("show_probability_in_ui", False)),
                            "data_hash": (engine.cls_meta or {}).get("data_hash")},
            "breakers_open": sorted(engine.policy.breaker_open), "last_error": engine.last_error,
            "open_incidents": sum(i.status in ("open", "awaiting_approval", "executing", "verifying")
                                  for i in engine.incidents)}


@app.get("/services")
def services():
    return {"services": engine.latest, "topology": config.TOPOLOGY, "depfail": {
        f"{a}->{b}": v for (a, b), v in engine.depfail.items()}}


@app.get("/incidents")
def incidents():
    with engine.lock:
        return [i.public() for i in engine.incidents]


@app.get("/incidents/{iid}")
def incident(iid: str):
    with engine.lock:
        i = next((x for x in engine.incidents if x.id == iid), None)
    if not i:
        raise HTTPException(404)
    return i.public()


@app.get("/approvals")
def approvals():
    with engine.lock:
        return [{"incident_id": i.id, "service": i.actions[-1]["service"], "runbook_id": i.actions[-1]["runbook_id"],
                 "risk": i.actions[-1]["risk"], "reason": i.actions[-1]["reason"], "cause": i.likely_cause,
                 "report": i.report} for i in engine.incidents if i.status == "awaiting_approval"]


@app.post("/approvals/{iid}/approve")
def approve(iid: str, who: Who, x_approval_token: str | None = Header(None)):
    _auth(x_approval_token)
    try:
        engine.approve(iid, who.approver)
    except ValueError as e:
        raise HTTPException(409, str(e))
    return {"ok": True}


@app.post("/approvals/{iid}/reject")
def reject(iid: str, who: Who, x_approval_token: str | None = Header(None)):
    _auth(x_approval_token)
    try:
        engine.reject(iid, who.approver)
    except ValueError as e:
        raise HTTPException(409, str(e))
    return {"ok": True}


@app.post("/mode")
def set_mode(m: Mode, x_approval_token: str | None = Header(None)):
    _auth(x_approval_token)
    if m.mode not in ("watch-only", "ask-first", "autopilot"):
        raise HTTPException(400, "mode must be watch-only, ask-first or autopilot")
    engine.policy.mode = m.mode
    return {"mode": m.mode}


@app.get("/audit")
def audit():
    return engine.executor.audit[-100:]


# ---- blind-challenge pass-through for the dashboard. The engine never reads these responses.
@app.post("/challenge/start")
def challenge_start():
    r = httpx.post(f"{EVALUATOR_URL}/runs", json={}, timeout=15)  # no scenario: the evaluator picks one itself
    r.raise_for_status()
    return r.json()


@app.get("/challenge/{run_id}/status")
def challenge_status(run_id: str):
    return httpx.get(f"{EVALUATOR_URL}/runs/{run_id}/status", timeout=10).json()


@app.get("/challenge/{run_id}/reveal")
def challenge_reveal(run_id: str):
    r = httpx.get(f"{EVALUATOR_URL}/runs/{run_id}/reveal", timeout=10)
    if r.status_code != 200:
        raise HTTPException(r.status_code, r.json().get("detail", "not available yet"))
    return r.json()


@app.get("/scorecard")
def scorecard():
    return httpx.get(f"{EVALUATOR_URL}/scorecard", timeout=10).json()
