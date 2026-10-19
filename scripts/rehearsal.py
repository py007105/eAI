"""Headless demo rehearsal driver (tooling only; no system code). Runs a plan of challenges against the running demo stack and records timings.

    python scripts/rehearsal.py --name R1 --plan r1 --token <throwaway token> [--emulate-dashboard]

The token is the one the brain container was started with (a throwaway for headless rehearsals, passed on the command line of this process only; it is never
printed or written). Plans:
  r1  (LLM on):   crash seed 2100 autopilot; hidden draw ask-first with a scripted approver; cpu_burn ask-first (proposal recorded and REJECTED, never approved);
                  traffic_surge ask-first (healthy: no incident expected)
  r2  (-NoLlm):   crash seed 2100 autopilot (same seed as r1 and as the live-LLM check set A); hidden draw autopilot; good_deploy autopilot (healthy)

For every challenge it records: seconds from the start request to the first incident, to verified recovery (the evaluator's score), to the scorecard showing the
run; minimum free RAM during the challenge; the Gemini requests the brain made (answered + failed attempts from each incident's report_meta); anything odd.
--emulate-dashboard polls the brain's REST endpoints every 2 s like the dashboard does (an emulation, not the real dashboard; the real one is R3).
"""
import argparse
import json
import secrets
import sys
import threading
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
import memguard  # noqa: E402
import stock_gate  # noqa: E402

EAI, EV = "http://localhost:8000", "http://localhost:8200"
POOL = ["crash", "latency", "error_spike", "memory_leak", "disk_fill", "bad_deploy", "traffic_surge", "good_deploy"]
HEALTHY = ("traffic_surge", "good_deploy")
TIMEOUT = {"memory_leak": 120, "disk_fill": 100}
PLANS = {
    "r1": [dict(label="supported fault, autopilot, fixed seed", scenario="crash", seed=2100, mode="autopilot", approve=False),
           dict(label="hidden supported/healthy draw, ask-first + scripted approver", scenario="hidden", mode="ask-first", approve=True),
           dict(label="UNSEEN fault cpu_burn, ask-first, proposal recorded and rejected", scenario="cpu_burn", mode="ask-first", approve=False),
           dict(label="healthy surge, ask-first", scenario="traffic_surge", mode="ask-first", approve=True)],
    "r2": [dict(label="supported fault, autopilot, fixed seed (template fallback)", scenario="crash", seed=2100, mode="autopilot", approve=False),
           dict(label="hidden supported/healthy draw, autopilot", scenario="hidden", mode="autopilot", approve=False),
           dict(label="healthy good_deploy, autopilot", scenario="good_deploy", mode="autopilot", approve=False)],
}


class Sampler(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.stop_ev, self.min_gb, self.errors, self.polls = threading.Event(), 99.0, 0, 0
        self.poll = False

    def run(self):
        n = 0
        while not self.stop_ev.is_set():
            self.min_gb = min(self.min_gb, memguard.free_ram_gb())
            if self.poll and n % 2 == 0:
                for path in ("/status", "/incidents", "/approvals", "/services"):
                    try:
                        httpx.get(EAI + path, timeout=5)
                        self.polls += 1
                    except httpx.HTTPError:
                        self.errors += 1
            n += 1
            time.sleep(1)


def call(method, url, token=None, **kw):
    h = {"X-Approval-Token": token} if token else {}
    return httpx.request(method, url, headers=h, timeout=20, **kw)


def run_step(step, token, smp, results):
    rec = {"label": step["label"], "mode": step["mode"]}
    scen = secrets.choice(POOL) if step["scenario"] == "hidden" else step["scenario"]
    rec["scenario_hidden_until_reveal"] = step["scenario"] == "hidden"
    r = call("POST", f"{EAI}/mode", token, json={"mode": step["mode"]})
    rec["mode_set"] = r.status_code
    rec["reset"] = call("POST", f"{EAI}/admin/reset", token).status_code
    try:
        rec["stock"] = stock_gate.gate()
    except stock_gate.GateError as e:
        rec["error"] = f"stock gate: {e}"
        return rec
    sc0 = call("GET", f"{EV}/scorecard").json().get("runs")
    smp.min_gb = 99.0
    t0 = time.time()
    body = {"scenario": scen, "timeout_s": TIMEOUT.get(scen, 90), "healthy_s": 60}
    if step.get("seed") is not None:
        body["seed"] = step["seed"]
    rid = call("POST", f"{EV}/runs", json=body).json()["run_id"]
    rec["run_id"] = rid
    approved, proposals, first_seen = [], [], {}
    state = "running"
    while state == "running" and time.time() - t0 < 400:
        try:
            for a in call("GET", f"{EAI}/approvals").json():
                iid = a["incident_id"]
                if iid not in first_seen:
                    first_seen[iid] = time.time()
                    proposals.append({"t_s": round(time.time() - t0, 1), **{k: a[k] for k in ("incident_id", "service", "runbook_id", "risk", "reason", "cause")},
                                      "report_summary": (a.get("report") or {}).get("summary")})
                if step["approve"] and iid not in approved and time.time() - first_seen[iid] >= 5:
                    p = call("POST", f"{EAI}/approvals/{iid}/approve", token, json={"approver": "rehearsal-operator"})
                    approved.append(iid)
                    rec.setdefault("approve_status", []).append(p.status_code)
        except (httpx.HTTPError, ValueError) as e:
            rec.setdefault("flakiness", []).append(f"approvals poll: {type(e).__name__}")
        state = call("GET", f"{EV}/runs/{rid}/status").json()["state"]
        time.sleep(2)
    t_fin = time.time()
    rev = call("GET", f"{EV}/runs/{rid}/reveal")
    if rev.status_code != 200:
        rec["error"] = f"reveal {rev.status_code}"
        return rec
    truth, score = rev.json()["truth"], rev.json()["score"]
    if step["scenario"] == "cpu_burn":                      # never leave an unseen-fault proposal pending, and never approve it
        for a in call("GET", f"{EAI}/approvals").json():
            rec["rejected"] = call("POST", f"{EAI}/approvals/{a['incident_id']}/reject", token, json={"approver": "rehearsal-operator"}).status_code
    while True:                                              # scorecard count
        n = call("GET", f"{EV}/scorecard").json().get("runs")
        if n is not None and sc0 is not None and n > sc0 or time.time() - t_fin > 60:
            break
        time.sleep(1)
    t_card = time.time()
    incs = [i for i in call("GET", f"{EAI}/incidents").json() if i["opened_t"] >= truth["t_inject"] - 1]
    for _ in range(40):                                      # let an in-flight LLM call finish (its own timeout is 20 s per provider)
        incs = [i for i in call("GET", f"{EAI}/incidents").json() if i["opened_t"] >= truth["t_inject"] - 1]
        if not any((i.get("report_meta") or {}).get("llm_pending") for i in incs):
            break
        time.sleep(2)
    gem = sum(((1 if (i.get("report_meta") or {}).get("provider") not in (None, "template") else 0) + len((i.get("report_meta") or {}).get("fallback_reasons") or []))
              for i in incs)
    rec.update({
        "revealed_scenario": truth["scenario"], "target": truth["target"], "supported": truth["supported"],
        "s_to_first_incident": round(incs[0]["opened_t"] - truth["t_inject"], 1) if incs else None,
        "s_to_verified_recovery": score.get("time_to_verified_recovery_s"), "recovered": score.get("recovered"),
        "detected": score.get("detected"), "time_to_detect_s": score.get("time_to_detect_s"), "failed_request_pct": score.get("failed_request_pct"),
        "incidents_opened": score.get("incidents_opened"), "actions_executed": score.get("actions_executed"), "abstained_correctly": score.get("abstained_correctly"),
        "s_start_to_run_finished": round(t_fin - t0, 1), "s_start_to_scorecard": round(t_card - t0, 1), "scorecard_incremented": (n or 0) > (sc0 or 0),
        "min_free_ram_gb": round(smp.min_gb, 2), "gemini_requests": gem,
        "providers": [(i.get("report_meta") or {}).get("provider") for i in incs],
        "fallback_reasons": [x for i in incs for x in ((i.get("report_meta") or {}).get("fallback_reasons") or [])],
        "executed": [f"{a['runbook_id']}@{a['service']}" for i in incs for a in i.get("actions", []) if a.get("executed")],
        "proposals": proposals,
        "diagnosis": [{"root": (i.get("diagnosis") or {}).get("root"), "ranking": i.get("ranking"), "abstained": i.get("abstained"),
                       "novelty": (i.get("diagnosis") or {}).get("novelty"), "threshold": (i.get("diagnosis") or {}).get("novelty_threshold"),
                       "confidence": i.get("confidence"), "status": i.get("status")} for i in incs]})
    time.sleep(25)                                            # let the evaluator restore the stack before the next challenge
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--plan", required=True, choices=list(PLANS))
    ap.add_argument("--token", required=True)
    ap.add_argument("--emulate-dashboard", action="store_true")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    out = Path(a.out or f"results/rehearsals/{a.name}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    smp = Sampler()
    smp.poll = a.emulate_dashboard
    smp.start()
    t0, results = time.time(), []
    status = call("GET", f"{EAI}/status").json()
    for step in PLANS[a.plan]:
        try:
            results.append(run_step(step, a.token, smp, results))
        except Exception as e:  # noqa: BLE001 - a rehearsal must record, not hide, what went wrong
            results.append({"label": step["label"], "error": f"{type(e).__name__}: {e}"})
        print(json.dumps({k: results[-1].get(k) for k in ("label", "revealed_scenario", "s_to_first_incident", "s_to_verified_recovery", "recovered", "error")}), flush=True)
    smp.stop_ev.set()
    doc = {"name": a.name, "plan": a.plan, "started": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(t0)), "total_s": round(time.time() - t0, 1),
           "brain": {k: status.get(k) for k in ("brain", "mode", "fallbacks_in_use")}, "emulated_dashboard_polls": smp.polls, "emulated_dashboard_errors": smp.errors,
           "steps": results}
    out.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
