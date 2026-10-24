"""Release-gate item G5 (docs/RELEASE_GATE.md): a forest-only anomaly must wait for approval. Controlled stimulus at the
detector boundary, measured on the live stack; the decision path is not touched.

    python scripts/live_check_g5.py [--scenarios error_spike latency]

Why a new stimulus (docs/results/v3_execution_20261024T001813-4cedc8bf.md): with only the learned limits emptied, the
forest's threshold (above every healthy validation score) was never reached by a real fault, so no forest-only incident
occurred. Here:
1. CALIBRATION on the unmodified candidate: web's live forest score (GET /services, the brain's own detector) is sampled
   for 60 s healthy, then during a real injected fault on web. `sustained` = the highest level the score held over
   SUSTAIN consecutive samples during the fault (an incident needs 3 consecutive anomalous ticks). If sustained does not
   exceed the healthy maximum by MIN_SEPARATION, the forest cannot separate this fault: G5 stays INCOMPLETE.
2. SUBSTITUTION (modified runtime configuration, recorded): in the running brain container,
   `models/artifacts/detectors.joblib` gets every service's learned limits emptied (as C2) and web's forest threshold set
   to the midpoint between the healthy maximum and `sustained`. Only data inside the container changes; image, source,
   anomaly_source(), the policy and the executor are the candidate's.
3. A real fault of the same scenario on web. PASS only if: an incident opened after the injection has
   anomaly_source == "forest_only"; its first proposal waits ("unusual combination", verdict needs_approval or
   expired_unapproved); no autopilot action is audited and Docker records no action on web between injection and end of
   the run. Nobody approves during the run.
4. In a `finally`, the brain is recreated from the image and verified (SHA256 of the three data files = this commit's,
   margin 0.121529).
Statuses PASS / FAIL / INCOMPLETE; only PASS counts. Controlled-path evidence only: it does not show that forest-only
anomalies occur naturally, nor generalisation.
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import subprocess
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import live_check_controlled as cc  # noqa: E402
import live_check_phase1 as lc  # noqa: E402
import live_check_phase4a as p4  # noqa: E402
import stack_lock  # noqa: E402

ROOT = lc.ROOT
OUT_MD = ROOT / "docs" / "results" / "live_check_g5.md"
OUT_JSON = ROOT / "results" / "live-checks" / "g5.json"
TARGET, HEALTHY_S, SUSTAIN, MIN_SEPARATION = "web", 60, 4, 0.01
checks = cc.checks


class ScoreSampler(threading.Thread):
    """Samples the brain's own forest score for one service from GET /services once a second."""

    def __init__(self, api, service):
        super().__init__(daemon=True)
        self.api, self.service, self.samples, self.stop_ev = api, service, [], threading.Event()

    def run(self):
        while not self.stop_ev.is_set():
            try:
                s = (self.api.get("/services").json().get("services") or {}).get(self.service) or {}
                if s.get("score") is not None:
                    self.samples.append((time.time(), float(s["score"])))
            except Exception:  # noqa: BLE001
                pass
            time.sleep(1)


def sustained_level(values: list[float], k: int) -> float | None:
    """The highest level held for k consecutive samples (max over windows of the window minimum)."""
    if len(values) < k:
        return None
    return max(min(values[i:i + k]) for i in range(len(values) - k + 1))


def threshold_from(healthy: list[float], fault: list[float], k: int = SUSTAIN, min_sep: float = MIN_SEPARATION) -> dict:
    hmax, sus = (max(healthy) if healthy else None), sustained_level(fault, k)
    ok = hmax is not None and sus is not None and sus - hmax > min_sep
    return {"healthy_max": hmax, "healthy_n": len(healthy), "fault_sustained": sus, "fault_n": len(fault),
            "fault_peak": max(fault) if fault else None, "separable": ok,
            "threshold": round((hmax + sus) / 2, 6) if ok else None}


def substitution_code(threshold: float) -> str:
    return ("import joblib; p='/srv/models/artifacts/detectors.joblib'; d=joblib.load(p); "
            "[setattr(v,'limits',{}) for v in d.values()]; old=d[%r].threshold; d[%r].threshold=%r; joblib.dump(d,p); "
            "print(old)") % (TARGET, TARGET, float(threshold))


def calibrate(api, env, scenario) -> dict:
    sampler = ScoreSampler(api, TARGET)
    sampler.start()
    time.sleep(HEALTHY_S)
    t_healthy_end = time.time()
    r = cc.run_controlled(api, env, scenario, TARGET)
    sampler.stop_ev.set()
    rev = {}
    try:
        rev = api.get(f"/runs/{r['run_id']}/reveal", base=lc.EV).json()
    except Exception:  # noqa: BLE001
        pass
    t0, t1 = rev.get("truth", {}).get("t_inject"), rev.get("score", {}).get("t_end")
    healthy = [v for t, v in sampler.samples if t <= t_healthy_end]
    fault = [v for t, v in sampler.samples if t0 and t1 and t0 <= t <= t1]
    return {"scenario": scenario, **threshold_from(healthy, fault), "t_inject": t0, "t_end": t1,
            "incidents": cc.summary(r["incidents"]), "audited_actions": r["audited_actions"]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenarios", nargs="*", default=["error_spike", "latency"])
    a = ap.parse_args()
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    approval, chaos = secrets.token_urlsafe(24), secrets.token_urlsafe(24)
    base = {k: v for k, v in os.environ.items() if k not in ("CHAOS_TOKEN", "ETERNALAI_APPROVAL_TOKEN")}
    env = {**base, "ETERNALAI_APPROVAL_TOKEN": approval, "CHAOS_TOKEN": chaos, "EAI_EVALUATOR_TOKEN": approval,
           "OTEL_SDK_DISABLED": "true", "ETERNALAI_MODE": "autopilot", "ETERNALAI_POLICY_FILE": ""}
    out = {"commit": commit, "execution_id": cc.EXEC_ID, "started": lc.now_ist(), "spec": "docs/RELEASE_GATE.md G5",
           "script": "scripts/live_check_g5.py"}
    stack_lock.take("main", "G5 controlled check", f"plan-complete@{commit}")
    api = lc.Api(approval)
    try:
        out["free_gb_at_start"] = round(p4.wait_memory(), 2)
        services = [s for s in lc.run(["docker", "compose", "config", "--services"], env).stdout.split() if s != "jaeger"]
        if lc.run(["docker", "compose", "up", "-d", "--force-recreate", *services], env, timeout=900).returncode:
            lc.check("setup.stack_up", "stack starts", False)
            return
        if not lc.check("setup.brain_up", "brain answers /status", cc.wait_brain(api)):
            return
        lc.run([sys.executable, "scripts/stock_gate.py", "--restock", "--force"], env, timeout=300)
        out["initial_state"] = cc.verify_restored(api, env)
        if not lc.check("setup.unmodified", "the brain starts with exactly this commit's files (SHA256) and margin 0.121529",
                        out["initial_state"]["restored"], out["initial_state"]):
            return
        cal = None
        out["calibration"] = []
        for scen in a.scenarios:
            c = calibrate(api, env, scen)
            out["calibration"].append(c)
            if c["separable"]:
                cal = c
                break
            cc.fresh_brain(api, env)          # a clean brain before the next calibration run
        if cal is None:
            cc.status_line("G5.calibration", "the live forest score separates a real fault on web from healthy (unmodified "
                           "candidate)", "INCOMPLETE", out["calibration"])
            cc.status_line("G5", "forest-only anomaly waits for approval", "INCOMPLETE", "no separable fault: not exercised")
            return
        cc.status_line("G5.calibration", "the live forest score separates a real fault on web from healthy (unmodified "
                       "candidate)", "PASS", cal)
        rec = {"file": "models/artifacts/detectors.joblib",
               "substitution": f"learned limits emptied for every service; {TARGET} forest threshold -> {cal['threshold']}"}
        try:
            cc.fresh_brain(api, env)
            sub = cc.brain_exec(substitution_code(cal["threshold"]), env)
            rec.update(substitution_exit=sub.returncode, original_threshold=(sub.stdout.strip().splitlines() or [None])[-1])
            lc.run(["docker", "restart", cc.BRAIN], env, timeout=120)
            rec["brain_up_after_substitution"] = cc.wait_brain(api)
            if sub.returncode != 0 or not rec["brain_up_after_substitution"]:
                cc.status_line("G5", "substitution could not be applied", "FAIL", rec)
                return
            r = cc.run_controlled(api, env, cal["scenario"], TARGET)
            forest = [i for i in r["incidents"] if (i.get("diagnosis") or {}).get("anomaly_source") == "forest_only"]
            rec.update(scenario=cal["scenario"], incidents=cc.summary(r["incidents"]), audited_actions=r["audited_actions"],
                       docker_actions_on_target=r["docker_actions_on_target"], forest_only_incidents=len(forest))
            if not forest:
                cc.status_line("G5", "controlled (modified runtime, detector boundary): no forest-only incident occurred",
                               "INCOMPLETE", rec)
                return
            waited = all(i.get("actions") and i["actions"][0].get("verdict") in ("needs_approval", "expired_unapproved")
                         and "unusual combination" in (i["actions"][0].get("reason") or "") for i in forest)
            executed = [a for i in forest for a in i.get("actions") or [] if a.get("executed")]
            unauthorised = [x for x in r["audited_actions"] if x[2] == "autopilot"] + list(r["docker_actions_on_target"])
            rec.update(first_actions=[(i.get("actions") or [{}])[0] for i in forest], executed=executed, unauthorised=unauthorised)
            cc.status_line("G5", "controlled (modified runtime, detector boundary): a forest-only incident on web waits for "
                           "approval ('unusual combination'); nothing executed; no autopilot action audited; no Docker action "
                           "on web", "PASS" if waited and not executed and not unauthorised else "FAIL", rec)
        finally:
            cc.fresh_brain(api, env)
            rec["restoration"] = cc.verify_restored(api, env)
            out["controlled"] = rec
            cc.status_line("G5.restore", "brain recreated from the image; files equal this commit (SHA256), margin 0.121529",
                           "PASS" if rec["restoration"]["restored"] else "FAIL", rec["restoration"])
        out["finished"] = lc.now_ist()
    finally:
        try:
            cc.fresh_brain(api, env)
            out["exit_state"] = cc.verify_restored(api, env)
        finally:
            lc.run(["docker", "compose", "stop"], env, timeout=300)
            stack_lock.release("main", f"plan-complete@{commit}")
            write(out)


def write(out):
    out["checks"] = checks
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")
    n = sum(c["result"] == "PASS" for c in checks)
    inc = sum(c["result"] == "INCOMPLETE" for c in checks)
    L = ["# G5 controlled check (generated by `scripts/live_check_g5.py`)", "",
         f"- Commit: `{out.get('commit')}`; execution ID: `{out.get('execution_id')}`; started {out.get('started')}, "
         f"finished {out.get('finished', 'not finished')}.",
         "- Modified runtime configuration during the check (inside the running brain container only): "
         "`models/artifacts/detectors.joblib` with the learned limits emptied and web's forest threshold set from the live "
         "calibration below. Image, source, anomaly_source(), policy and executor unchanged; nobody approved.",
         "- Controlled-path evidence only: not evidence that forest-only anomalies occur naturally, nor of generalisation.",
         f"- Result: **{n} of {len(checks)} checks passed**; INCOMPLETE: {inc}. Raw record: `results/live-checks/g5.json`.",
         "", "| check | what | result | detail |", "|---|---|---|---|"]
    for c in checks:
        d = c["detail"] if isinstance(c["detail"], str) else json.dumps(c["detail"], default=str)
        L.append(f"| `{c['id']}` | {c['what']} | {c['result']} | {d.replace('|', '/')[:1200]} |")
    OUT_MD.write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
