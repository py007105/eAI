"""Independent evaluator service: injects faults, keeps ground truth private, scores EternalAI.

Ground truth is written to /truth (a volume only this container mounts) and is never returned
by an endpoint until a run has finished. The blind challenge picks a scenario and target here;
the caller (and EternalAI) only get a run id.
"""
from __future__ import annotations

import hmac
import json
import os
import random
import threading
import time
import uuid
from pathlib import Path

import httpx
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

from scenarios import HEALTHY_SCENARIOS, SCENARIOS, SERVICES, Injector
from scoring import aggregate, score_run
from timing import settle_seconds

PROM = os.getenv("PROMETHEUS_URL", "http://prometheus:9090")
EAI = os.getenv("EAI_URL", "http://host.docker.internal:8000")
TRUTH = Path(os.getenv("TRUTH_DIR", "/truth"))  # a volume only this container mounts
TRUTH.mkdir(parents=True, exist_ok=True)
RESULTS = TRUTH / "results.jsonl"

DEFAULT_CHAOS_TOKEN = "evaluator-only"   # the old published default: anyone who read the repository knew it


def chaos_token() -> str:
    """The token the evaluator sends to the services' /_chaos endpoint. Refuse to start without a real one."""
    tok = os.getenv("CHAOS_TOKEN", "")
    if not tok or tok == DEFAULT_CHAOS_TOKEN:
        raise RuntimeError("CHAOS_TOKEN is unset or the published default 'evaluator-only'; set a real secret in .env. Refusing to start.")
    return tok


def _auth(token: str | None):
    """Starting a run injects a real fault, so it needs the same approval token as the brain's write endpoints."""
    good = os.getenv("ETERNALAI_APPROVAL_TOKEN", "")
    if not good or good == "change-me":
        raise HTTPException(503, "starting runs is disabled: set ETERNALAI_APPROVAL_TOKEN to a real secret")
    if not token or not hmac.compare_digest(token, good):
        raise HTTPException(403, "invalid approval token")


app = FastAPI(title="eai-evaluator")
inj = Injector(chaos_token())
runs: dict[str, dict] = {}
_state = {"after_deploy": False}  # the previous run left a release change behind
_lock = threading.Lock()


class RunRequest(BaseModel):
    scenario: str | None = None   # omit for a blind pick
    target: str | None = None
    seed: int | None = None
    timeout_s: int = 150
    healthy_s: int = 60           # observation time for healthy-negative scenarios
    # Opt-in, for the forecast check only (benchmarks leave both unset, so their runs behave exactly as before):
    variant: str | None = None    # "gradual" for disk_fill: a slow steady fill instead of the 30 s burst
    observe_full: bool = False    # observe until timeout_s even after the brain closed its incidents (no early end)


def _eai_incidents():
    try:
        return httpx.get(f"{EAI}/incidents", timeout=5).json()
    except (httpx.HTTPError, ValueError):
        return None


def _failed_pct(t0, t1):
    w = max(int(t1 - t0), 5)
    try:
        def q(expr):
            r = httpx.get(f"{PROM}/api/v1/query", params={"query": expr, "time": t1}, timeout=10).json()
            return float(r["data"]["result"][0]["value"][1]) if r["data"]["result"] else 0.0
        bad = q(f'sum(increase(loadgen_requests_total{{outcome="error"}}[{w}s]))')
        tot = q(f'sum(increase(loadgen_requests_total[{w}s]))')
        return round(100 * bad / tot, 2) if tot else None
    except (httpx.HTTPError, KeyError, ValueError):
        return None


def _wait_quiet(max_s=90):
    """Wait until EternalAI has no open incident, so the next run starts from a calm system."""
    end, misses = time.time() + max_s, 0
    while time.time() < end:
        inc = _eai_incidents()
        if inc is None:
            misses += 1
            if misses >= 3:  # EternalAI is not running; nothing to wait for
                return False
        elif not any(i["status"] in ("open", "awaiting_approval", "executing", "verifying") for i in inc):
            return True
        time.sleep(2)
    return False


def _execute(run_id: str, req: RunRequest):
    st = runs[run_id]
    rng = random.Random(st["seed"])
    scen, target = st["_scenario"], st["_target"]
    expected, supported, _ = SCENARIOS[scen]
    try:
        changed = inj.restore(set())
        _wait_quiet()
        # let rate windows fill with healthy data; after a release change also let the 3-minute
        # "recent deploy" signal expire so one run cannot leak into the next
        time.sleep(settle_seconds(changed, _state["after_deploy"]))
        t_inject = time.time()
        params = inj.inject(scen, target, rng, req.variant) if req.variant else inj.inject(scen, target, rng)
        truth = {"run_id": run_id, "scenario": scen, "target": target, "expected_label": expected,
                 "supported": supported, "t_inject": t_inject, "params": params, "seed": st["seed"]}
        (TRUTH / f"{run_id}.json").write_text(json.dumps(truth))
        deadline = t_inject + (req.healthy_s if scen in HEALTHY_SCENARIOS else req.timeout_s)
        while time.time() < deadline:
            time.sleep(2)
            if scen not in HEALTHY_SCENARIOS and not req.observe_full:
                inc = [i for i in (_eai_incidents() or []) if i["opened_t"] >= t_inject - 1]
                if inc and all(i["status"] in ("recovered", "partially_recovered", "unresolved", "escalated")
                               for i in inc) and time.time() - max(i["closed_t"] or 0 for i in inc) > 8:
                    break
        t_end = time.time()
        incidents = _eai_incidents() or []
        res = score_run(truth, incidents, _failed_pct(t_inject, t_end), t_end)
        res["t_end"] = t_end  # end of the observation window, before the restore that follows
        with _lock, RESULTS.open("a") as f:
            f.write(json.dumps(res) + "\n")
        st["_result"] = res
    except Exception as e:
        st["error"] = f"{type(e).__name__}: {e}"
    finally:
        # The run only counts as finished AFTER the stack has been restored. Marking it finished first let the
        # caller start the next run while this restore was still recreating containers: two restores collided
        # ("expected 1 container ..., found 0") and about 1 in 8 collection runs failed.
        try:
            _wait_quiet(30)   # let the brain finish any action in flight; restoring underneath it caused a 409 race
            nxt = inj.restore({target})
            _state["after_deploy"] = nxt or scen in ("bad_deploy", "good_deploy")
        except Exception as e:
            st.setdefault("error", f"restore failed: {type(e).__name__}: {e}")
            st.pop("_result", None)
        st["state"] = "finished" if "_result" in st else "failed"


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/runs")
def start(req: RunRequest, x_approval_token: str | None = Header(None)):
    _auth(x_approval_token)
    if any(r["state"] == "running" for r in runs.values()):
        raise HTTPException(409, "a run is already in progress")
    rng = random.Random(req.seed)
    scen = req.scenario or rng.choice(list(SCENARIOS))
    if scen not in SCENARIOS:
        raise HTTPException(400, f"unknown scenario {scen}")
    if req.variant is not None and (req.variant, scen) != ("gradual", "disk_fill"):
        raise HTTPException(400, "the only variant is 'gradual', for disk_fill")
    target = req.target or rng.choice(SCENARIOS[scen][2])
    if target not in SERVICES:
        raise HTTPException(400, f"unknown target {target}")
    run_id = uuid.uuid4().hex[:10]
    seed = req.seed if req.seed is not None else rng.randrange(1 << 30)
    # the truth fields start with "_" and are never serialised by /status
    runs[run_id] = {"run_id": run_id, "state": "running", "started": time.time(), "seed": seed,
                    "blind": req.scenario is None, "_scenario": scen, "_target": target}
    threading.Thread(target=_execute, args=(run_id, req), daemon=True).start()
    return {"run_id": run_id, "blind": runs[run_id]["blind"]}


@app.get("/runs/{run_id}/status")
def status(run_id: str):
    r = runs.get(run_id)
    if not r:
        raise HTTPException(404)
    return {k: v for k, v in r.items() if not k.startswith("_") and k != "seed"} | {
        "elapsed_s": round(time.time() - r["started"], 1)}


@app.get("/runs/{run_id}/reveal")
def reveal(run_id: str):
    r = runs.get(run_id)
    if not r:
        raise HTTPException(404)
    if r["state"] != "finished":
        raise HTTPException(409, f"run is {r['state']}; the truth is revealed only after scoring")
    truth = json.loads((TRUTH / f"{run_id}.json").read_text())
    return {"truth": truth, "score": r["_result"]}


@app.get("/scorecard")
def scorecard():
    rows = [json.loads(line) for line in RESULTS.read_text().splitlines()] if RESULTS.exists() else []
    return {"runs": len(rows), "by_scenario": aggregate(rows)}
