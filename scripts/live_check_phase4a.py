"""Phase 4a live check (docs/LIVE_CHECK_PHASE4A.md): forest-only -> approval, close root candidates -> abstain, learn store,
POST /feedback, on the real Compose stack. No fakes.

    python scripts/live_check_phase4a.py [--no-build]

Reuses the helpers of scripts/live_check_phase1.py (throwaway tokens through the environment only, never printed or written).
Takes and releases the shared Docker lock (scripts/stack_lock.py) and waits for at least 1.8 GB of free RAM.
"""
from __future__ import annotations

import argparse
import ctypes
import json
import os
import secrets
import subprocess
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
import live_check_phase1 as lc  # noqa: E402
import stack_lock  # noqa: E402

ROOT = lc.ROOT
OUT_MD = ROOT / "docs" / "results" / "live_check_phase4a.md"
OUT_JSON = ROOT / "results" / "live-checks" / "phase4a.json"
MARGIN = 0.121529
MIN_FREE_GB = 1.8
check, checks, EAI = lc.check, lc.checks, lc.EAI


def free_gb() -> float:
    class MS(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong), ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong), ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong), ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong), ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
    m = MS()
    m.dwLength = ctypes.sizeof(MS)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
    return m.ullAvailPhys / 1e9


def wait_memory(limit_s=1800):
    t0 = time.time()
    while free_gb() < MIN_FREE_GB and time.time() - t0 < limit_s:
        print(f"{lc.now_ist()} waiting: {free_gb():.1f} GB free, need {MIN_FREE_GB}", flush=True)
        time.sleep(30)
    return free_gb()


def run_scenario(api, scenario, target, decide=None):
    """Start an evaluator run; `decide(proposal)` is called once for the first pending proposal on `target`."""
    t0 = time.time()
    rid = lc.start_run(api, scenario, target)
    seen = {}

    def tick(_st):
        if "proposal" in seen or decide is None:
            return
        for p in api.get("/approvals").json():
            if p["service"] == target:
                seen["proposal"] = p
                time.sleep(5)    # pending for a few seconds: nothing may run on its own
                seen["executed_before"] = [a for a in lc.audit_since(api, t0) if a.get("service") == target and "ok" in a]
                seen["decision_http"] = decide(p)
    rev = lc.wait_run(api, rid, tick)
    t_inj = rev.get("truth", {}).get("t_inject", t0)
    incs = [i for i in api.get("/incidents").json() if i["opened_t"] >= t_inj - 1]
    return {"run_id": rid, "scenario": scenario, "target": target, "score": rev.get("score"), "incidents": incs,
            "audit": lc.audit_since(api, t0), **seen}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-build", action="store_true")
    a = ap.parse_args()
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    approval, chaos = secrets.token_urlsafe(24), secrets.token_urlsafe(24)
    base = {k: v for k, v in os.environ.items() if k not in ("CHAOS_TOKEN", "ETERNALAI_APPROVAL_TOKEN")}
    env = {**base, "ETERNALAI_APPROVAL_TOKEN": approval, "CHAOS_TOKEN": chaos, "EAI_EVALUATOR_TOKEN": approval,
           "OTEL_SDK_DISABLED": "true", "ETERNALAI_MODE": "autopilot", "ETERNALAI_POLICY_FILE": ""}
    out = {"commit": commit, "started": lc.now_ist(), "spec": "docs/LIVE_CHECK_PHASE4A.md"}
    stack_lock.take("main", "Phase 4a live check", f"plan-complete@{commit}")
    try:
        out["free_gb_at_start"] = round(wait_memory(), 2)
        if not a.no_build:
            r = lc.run(["docker", "compose", "build", "eternalai"], env, timeout=1800)
            if r.returncode:
                check("setup.build", "brain image builds from this commit", False, r.stderr[-300:])
                return
        services = [s for s in lc.run(["docker", "compose", "config", "--services"], env).stdout.split() if s != "jaeger"]
        r = lc.run(["docker", "compose", "up", "-d", "--force-recreate", *services], env, timeout=900)
        if r.returncode:
            check("setup.stack_up", "stack starts", False, r.stderr[-300:])
            return
        api = lc.Api(approval)
        if not check("setup.brain_up", "brain answers /status", lc.wait_status(api) is not None):
            return
        time.sleep(45)
        r = lc.run([sys.executable, "scripts/stock_gate.py", "--restock", "--force"], env, timeout=300)
        check("setup.stock", "inventory restocked and verified", r.returncode == 0, r.stdout.strip()[-100:])
        st = api.get("/status").json()
        out["status"] = {k: st.get(k) for k in ("mode", "root_margin", "learn_store", "models")}
        out["status"]["policy_file"] = (st.get("policy") or {}).get("file")
        check("A1", "margin 0.121529 loaded, learn store open, default rulebook, autopilot",
              st.get("root_margin") is not None and abs(st["root_margin"] - MARGIN) < 1e-6
              and not (st.get("learn_store") or {}).get("error") and (st.get("policy") or {}).get("file") == "default.yaml"
              and st.get("mode") == "autopilot", out["status"])
        stats0 = api.get("/learn/stats").json()

        runs = [run_scenario(api, "crash", "web"),
                run_scenario(api, "crash", "payments",
                             decide=lambda p: api.post(f"/approvals/{p['incident_id']}/reject", json={"approver": "live-check"}).status_code),
                run_scenario(api, "error_spike", "orders",
                             decide=lambda p: api.post(f"/approvals/{p['incident_id']}/approve", json={"approver": "live-check"}).status_code)]
        out["runs"] = [{k: v for k, v in r.items() if k not in ("incidents", "audit")} for r in runs]
        incs = [i for r in runs for i in r["incidents"]]
        diag = [i for i in incs if i.get("diagnosis")]
        out["incidents"] = [{"id": i["id"], "status": i["status"], "cause": i["likely_cause"], "abstained": i["abstained"],
                             "anomaly_source": (i["diagnosis"] or {}).get("anomaly_source"),
                             "root_gap": (i["diagnosis"] or {}).get("root_gap"), "root": (i["diagnosis"] or {}).get("root"),
                             "abstain_reason": (i["diagnosis"] or {}).get("abstain_reason"),
                             "actions": [(x.get("runbook_id"), x.get("service"), x.get("verdict"), x.get("executed")) for x in i["actions"]]}
                            for i in incs]
        check("A2", "every diagnosed incident records anomaly_source, root_gap and root_margin",
              bool(diag) and all((i["diagnosis"].get("anomaly_source") in ("down", "limits", "forest_only", "none"))
                                 and i["diagnosis"].get("root_gap") is not None
                                 and abs((i["diagnosis"].get("root_margin") or 0) - MARGIN) < 1e-6 for i in diag),
              {"diagnosed": len(diag), "sources": sorted({i["diagnosis"].get("anomaly_source") for i in diag})})
        close = [i for i in diag if i["diagnosis"]["root_gap"] < MARGIN]
        close_abst = [i for i in diag if "two close root candidates" in (i["diagnosis"].get("abstain_reason") or "")]
        forest = [i for i in diag if i["diagnosis"].get("anomaly_source") == "forest_only"]
        forest_auto = [i for i in forest if any(x.get("executed") and x.get("verdict") == "execute" for x in i["actions"])]
        check("A3", "close candidates abstain exactly when gap < margin; no forest-only incident ran automatically",
              all(i["abstained"] for i in close) and all(i["diagnosis"]["root_gap"] < MARGIN for i in close_abst)
              and not forest_auto,
              {"close_gap_incidents": len(close), "abstained_close": len(close_abst), "forest_only": len(forest),
               "forest_only_auto_executed": len(forest_auto),
               "label_close": "triggered live" if close else "active and consistent live, not triggered",
               "label_forest": "triggered live" if forest else "active and consistent live, not triggered"})
        r1, r2, r3 = runs
        a1 = [x for x in r1["audit"] if x.get("runbook") == "restart_service" and x.get("service") == "web" and x.get("ok")]
        check("A4", "crash on web: restart_service executed by autopilot", any(x.get("actor") == "autopilot" for x in a1),
              [(x.get("runbook"), x.get("actor")) for x in r1["audit"] if "ok" in x])
        p2 = r2.get("proposal") or {}
        ex2 = [x for x in r2["audit"] if x.get("service") == "payments" and "ok" in x]
        check("A5", "crash on payments: waits as protected; rejected; escalated; nothing executed on payments",
              "protected" in (p2.get("reason") or "") and r2.get("decision_http") == 200 and not ex2
              and any(i["status"] == "escalated" for i in r2["incidents"]),
              {"reason": p2.get("reason"), "reject_http": r2.get("decision_http"), "executed": len(ex2)})
        p3 = r3.get("proposal") or {}
        ex3 = [x for x in r3["audit"] if x.get("service") == "orders" and x.get("ok")]
        check("A6", "error_spike on orders: waits (medium); nothing before approval; executed by human:live-check after",
              p3.get("risk") in ("medium", "high") and r3.get("executed_before") == [] and r3.get("decision_http") == 200
              and any(x.get("actor") == "human:live-check" for x in ex3),
              {"proposal": {k: p3.get(k) for k in ("runbook_id", "risk", "reason")}, "approve_http": r3.get("decision_http"),
               "executed_before": len(r3.get("executed_before") or []), "executed_after": [(x["runbook"], x["actor"]) for x in ex3]})

        time.sleep(6)   # the engine writes closed incidents to the store on its next ticks
        final = {i["id"]: i for i in api.get("/incidents").json() if i["id"] in {x["id"] for x in incs}}
        closed = [i for i in final.values() if i["status"] in ("recovered", "partially_recovered", "unresolved", "escalated")]
        mism = []
        for i in closed:
            rec = api.get(f"/learn/{i['id']}")
            if rec.status_code != 200:
                mism.append((i["id"], "missing"))
                continue
            rec = rec.json()
            if rec["status"] != i["status"] or [x["verdict"] for x in rec["actions"]] != [x["verdict"] for x in i["actions"]]:
                mism.append((i["id"], "differs"))
            if i.get("diagnosis") and i["diagnosis"].get("root") and not json.loads(rec.get("root_features") or "{}"):
                mism.append((i["id"], "no root_features"))
            if any(x.get("executed") for x in i["actions"]) and i.get("verification") and not rec.get("outcome"):
                mism.append((i["id"], "no outcome"))
        stats1 = api.get("/learn/stats").json()
        out["learn_stats"] = {"before": stats0, "after": stats1}
        check("B1", "every closed incident of the runs is in the learn store and matches /incidents",
              bool(closed) and not mism, {"closed": len(closed), "mismatches": mism, "stats_before": stats0, "stats_after": stats1})
        target = closed[0]["id"] if closed else "none"
        body = {"approver": "live-check", "confirmed": False, "correct_fault": "error_spike", "note": "live check feedback"}
        c_no = httpx.post(f"{EAI}/feedback/{target}", json=body, timeout=10).status_code
        c_404 = api.post("/feedback/no-such-incident", json=body).status_code
        c_ok = api.post(f"/feedback/{target}", json=body).status_code
        fb = api.get(f"/learn/{target}").json().get("feedback", []) if closed else []
        check("B2", "POST /feedback: 403 without token, 404 unknown id, 200 with token, visible in /learn/{id}",
              c_no == 403 and c_404 == 404 and c_ok == 200 and any(f.get("correct_fault") == "error_spike" for f in fb),
              {"no_token": c_no, "unknown": c_404, "ok": c_ok, "feedback_rows": len(fb)})
        out["finished"] = lc.now_ist()
    finally:
        lc.run(["docker", "compose", "stop"], env, timeout=300)
        stack_lock.release("main", f"plan-complete@{commit}")
        write(out)


def write(out):
    out["checks"] = checks
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")
    n = sum(c["result"] == "PASS" for c in checks)
    lines = ["# Phase 4a live check (generated by `scripts/live_check_phase4a.py`)", "",
             f"- Specification (written before the run): `docs/LIVE_CHECK_PHASE4A.md`.",
             f"- Commit and brain image: `{out.get('commit')}`; started {out.get('started')}, finished {out.get('finished', 'not finished')}.",
             f"- Free RAM at start: {out.get('free_gb_at_start')} GB. Rulebook `default.yaml`, autopilot, telemetry condition T3.",
             f"- Result: **{n} of {len(checks)} checks passed.** Raw record: `results/live-checks/phase4a.json`.", "",
             "| check | what | result | detail |", "|---|---|---|---|"]
    for c in checks:
        d = c["detail"] if isinstance(c["detail"], str) else json.dumps(c["detail"], default=str)
        lines.append(f"| `{c['id']}` | {c['what']} | {c['result']} | {d.replace('|', '/')[:700]} |")
    lines += ["", "Standing limit: none of this shows safety on unseen faults (`docs/postmortems/cpu_burn_seed426.md`; the "
              "close-candidates margin would not have caught that case)."]
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{n}/{len(checks)} passed; wrote {OUT_MD.relative_to(ROOT)}", flush=True)


if __name__ == "__main__":
    main()
