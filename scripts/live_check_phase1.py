"""Phase 1 live check: safety and policy on the real Docker Compose stack (no fakes, no mocks).

    python scripts/live_check_phase1.py [--no-up] [--keep-running]

What it does, in order (each check is PASS or FAIL in docs/results/live_check_phase1.md):
  1. compose refuses to start without CHAOS_TOKEN; the shop and evaluator images refuse the old default token
  2. starts the stack (telemetry condition T3, as scripts/demo.ps1: no Jaeger, trace export off) with a throwaway approval
     token and a throwaway chaos token generated here and passed through the environment only (never printed or written),
     autopilot mode, the default rulebook; restocks inventory (scripts/stock_gate.py)
  3. every published port is bound to 127.0.0.1; /status shows the plan rulebook
  4. fault start without / with a wrong token is refused (brain /challenge/start, evaluator /runs)
  5. kill switch: on -> watch-only, leaving watch-only refused, off
  6. four real evaluator runs:
       crash on web           -> low risk, autopilot executes, verified
       crash on payments      -> protected: waits for approval; rejected -> escalated, nothing executed
       crash on inventory     -> with the kill switch on: blocked, nothing executed
       bad_deploy on orders   -> rollback is high risk: waits for approval, not executed until approved; approved -> executed
  7. the audit trail has the policy reason and the verification results
  8. GET /approvals stays fast while the brain diagnoses (polled every 0.25 s through all runs)
  9. Prometheus stopped: the brain keeps ticking, reports the failed queries, opens no incident
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
DOCKER_BIN = r"C:\Program Files\Docker\Docker\resources\bin"
EAI, EV = "http://localhost:8000", "http://localhost:8200"
OUT_MD = ROOT / "docs" / "results" / "live_check_phase1.md"
OUT_JSON = ROOT / "results" / "live-checks" / "phase1.json"
IST = timezone(timedelta(hours=5, minutes=30))

checks: list[dict] = []


def now_ist() -> str:
    return datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S IST")


def check(cid: str, what: str, ok: bool, detail="") -> bool:
    checks.append({"id": cid, "what": what, "result": "PASS" if ok else "FAIL", "detail": detail, "t": now_ist()})
    print(f"[{'PASS' if ok else 'FAIL'}] {cid}: {what} {('- ' + str(detail)) if detail else ''}", flush=True)
    return ok


def run(cmd: list[str], env: dict, timeout=900) -> subprocess.CompletedProcess:
    e = {**env, "PATH": env.get("PATH", "") + os.pathsep + DOCKER_BIN}
    return subprocess.run(cmd, cwd=ROOT, env=e, capture_output=True, text=True, timeout=timeout)


# ------------------------------------------------------------------ API helpers
class Api:
    def __init__(self, token: str):
        self.h = {"X-Approval-Token": token}

    def get(self, path, base=EAI, **kw):
        return httpx.get(base + path, timeout=15, **kw)

    def post(self, path, base=EAI, auth=True, **kw):
        return httpx.post(base + path, timeout=20, headers=self.h if auth else {}, **kw)


class LatencyProbe(threading.Thread):
    """Polls GET /approvals every 0.25 s and keeps the latencies."""

    def __init__(self):
        super().__init__(daemon=True)
        self.lat, self.errors, self.stop_ev = [], 0, threading.Event()

    def run(self):
        with httpx.Client(timeout=5) as c:
            while not self.stop_ev.is_set():
                t0 = time.perf_counter()
                try:
                    c.get(f"{EAI}/approvals").raise_for_status()
                    self.lat.append(time.perf_counter() - t0)
                except httpx.HTTPError:
                    self.errors += 1
                time.sleep(0.25)


def wait_status(api: Api, timeout=240) -> dict | None:
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            st = api.get("/status").json()
            if "policy" in st:
                return st
        except (httpx.HTTPError, ValueError):
            pass
        time.sleep(3)
    return None


def start_run(api: Api, scenario: str, target: str, timeout_s=150) -> str:
    r = api.post("/runs", base=EV, json={"scenario": scenario, "target": target, "timeout_s": timeout_s, "healthy_s": 60})
    r.raise_for_status()
    return r.json()["run_id"]


def run_state(api: Api, rid: str) -> dict:
    return api.get(f"/runs/{rid}/status", base=EV).json()


def wait_run(api: Api, rid: str, on_tick=None, limit_s=900) -> dict:
    t0 = time.time()
    while time.time() - t0 < limit_s:
        st = run_state(api, rid)
        if on_tick:
            on_tick(st)
        if st.get("state") != "running":
            break
        time.sleep(1)
    for _ in range(30):
        r = api.get(f"/runs/{rid}/reveal", base=EV)
        if r.status_code == 200:
            return r.json()
        time.sleep(2)
    return {}


def incidents_since(api: Api, t: float) -> list[dict]:
    return [i for i in api.get("/incidents").json() if i["opened_t"] >= t - 1]


def audit_since(api: Api, t: float) -> list[dict]:
    return [a for a in api.get("/audit").json() if a.get("t", 0) >= t]


def short(inc: dict) -> dict:
    a = (inc.get("actions") or [{}])[-1]
    return {"id": inc["id"], "status": inc["status"], "cause": inc["likely_cause"], "services": inc["services"],
            "action": {k: a.get(k) for k in ("runbook_id", "service", "verdict", "risk", "reason", "executed", "approved_by")},
            "verification": (inc.get("verification") or {}).get("outcome")}


# ------------------------------------------------------------------ scenarios
def scenario_autopilot_low(api: Api, out: dict):
    t0 = time.time()
    rid = start_run(api, "crash", "web")
    rev = wait_run(api, rid)
    incs = [short(i) for i in incidents_since(api, rev.get("truth", {}).get("t_inject", t0))]
    out["crash_web"] = {"run_id": rid, "score": rev.get("score"), "incidents": incs}
    acts = [i["action"] for i in incs if i["action"].get("service") == "web"]
    ok = any(a["verdict"] == "execute" and a["executed"] and a["risk"] == "low" for a in acts) and \
        any(i["status"] == "recovered" for i in incs)
    check("live.autopilot_low_executes", "crash on web: low-risk restart executed by autopilot and verified", ok,
          {"incidents": [(i["status"], i["action"].get("runbook_id"), i["action"].get("verdict")) for i in incs]})


def scenario_protected(api: Api, out: dict):
    t0 = time.time()
    rid = start_run(api, "crash", "payments")
    seen = {}

    def tick(_st):
        if "proposal" in seen:
            return
        for p in api.get("/approvals").json():
            if p["service"] == "payments":
                seen["proposal"] = p
                seen["audit_before"] = [a for a in audit_since(api, t0) if a.get("service") == "payments" and "ok" in a]
                seen["reject"] = api.post(f"/approvals/{p['incident_id']}/reject", json={"approver": "live-check"}).status_code
    rev = wait_run(api, rid, tick)
    incs = [short(i) for i in incidents_since(api, rev.get("truth", {}).get("t_inject", t0))]
    out["crash_payments"] = {"run_id": rid, "score": rev.get("score"), "incidents": incs,
                             "proposal": {k: seen.get("proposal", {}).get(k) for k in ("runbook_id", "risk", "reason")}}
    p = seen.get("proposal") or {}
    executed = [a for a in audit_since(api, t0) if a.get("service") == "payments" and "ok" in a]
    ok = bool(p) and "protected" in p.get("reason", "") and p.get("risk") == "low" and seen.get("reject") == 200 \
        and not executed and any(i["status"] == "escalated" for i in incs)
    check("live.protected_waits", "crash on payments (protected): low risk but waits for approval; rejected; nothing executed", ok,
          {"proposal": out["crash_payments"]["proposal"], "reject_http": seen.get("reject"), "executed_on_payments": len(executed)})


def scenario_killswitch(api: Api, out: dict):
    t0 = time.time()
    k = api.post("/killswitch", json={"on": True}).json()
    rid = start_run(api, "crash", "inventory")
    rev = wait_run(api, rid)
    incs = [short(i) for i in incidents_since(api, rev.get("truth", {}).get("t_inject", t0))]
    executed = [a for a in audit_since(api, t0) if "ok" in a]
    api.post("/killswitch", json={"on": False})
    back = api.post("/mode", json={"mode": "autopilot"}).status_code
    out["crash_inventory_killswitch"] = {"run_id": rid, "score": rev.get("score"), "incidents": incs, "killswitch": k}
    ok = k.get("mode") == "watch-only" and not executed and incs and \
        all(i["action"].get("verdict") in ("blocked", None) for i in incs) and \
        any("kill switch" in (i["action"].get("reason") or "") for i in incs) and back == 200
    check("live.killswitch_blocks", "kill switch on, crash on inventory: proposal blocked, nothing executed; back to autopilot after", ok,
          {"incidents": [(i["status"], i["action"].get("verdict"), i["action"].get("reason")) for i in incs],
           "executed": len(executed), "mode_restored_http": back})


def scenario_high_risk(api: Api, out: dict):
    t0 = time.time()
    rid = start_run(api, "bad_deploy", "orders")
    seen = {}

    def tick(_st):
        if "proposal" in seen:
            return
        for p in api.get("/approvals").json():
            if p["runbook_id"] == "rollback_release":
                seen["proposal"] = p
                time.sleep(5)    # leave it pending for a few seconds: autopilot must not run it on its own
                seen["executed_before"] = [a for a in audit_since(api, t0) if a.get("runbook") == "rollback_release" and "ok" in a]
                seen["approve"] = api.post(f"/approvals/{p['incident_id']}/approve", json={"approver": "live-check"}).status_code
    rev = wait_run(api, rid, tick)
    incs = [short(i) for i in incidents_since(api, rev.get("truth", {}).get("t_inject", t0))]
    after = [a for a in audit_since(api, t0) if a.get("runbook") == "rollback_release" and "ok" in a]
    out["bad_deploy_orders"] = {"run_id": rid, "score": rev.get("score"), "incidents": incs,
                                "proposal": {k: (seen.get("proposal") or {}).get(k) for k in ("service", "runbook_id", "risk", "reason")}}
    p = seen.get("proposal") or {}
    ok = p.get("risk") == "high" and seen.get("executed_before") == [] and seen.get("approve") == 200 and \
        any(a.get("ok") and a.get("actor") == "human:live-check" for a in after)
    check("live.high_risk_needs_approval", "bad_deploy on orders in autopilot: rollback (high) waits; runs only after approval", ok,
          {"proposal": out["bad_deploy_orders"]["proposal"], "executed_before_approval": len(seen.get("executed_before") or []),
           "approve_http": seen.get("approve"), "verification": [i["verification"] for i in incs]})


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-up", action="store_true", help="the stack is already running with tokens from this shell")
    ap.add_argument("--keep-running", action="store_true")
    a = ap.parse_args()
    approval, chaos = secrets.token_urlsafe(24), secrets.token_urlsafe(24)
    base_env = {k: v for k, v in os.environ.items() if k not in ("CHAOS_TOKEN", "ETERNALAI_APPROVAL_TOKEN")}
    env = {**base_env, "ETERNALAI_APPROVAL_TOKEN": approval, "CHAOS_TOKEN": chaos, "OTEL_SDK_DISABLED": "true",
           "ETERNALAI_MODE": "autopilot", "ETERNALAI_POLICY_FILE": "", "EAI_EVALUATOR_TOKEN": approval}
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    started = now_ist()
    out: dict = {"commit": commit, "started": started}

    # 1. refusals before anything starts
    with tempfile.TemporaryDirectory() as d:
        empty = Path(d) / "empty.env"
        empty.write_text("", encoding="utf-8")
        r = run(["docker", "compose", "--env-file", str(empty), "config", "-q"], base_env)
    check("startup.compose_requires_chaos_token", "docker compose refuses to start without CHAOS_TOKEN",
          r.returncode != 0 and "CHAOS_TOKEN" in r.stderr, r.stderr.strip().splitlines()[0][:160] if r.stderr else "")
    for img in ("eai/web:v1", "eai/evaluator:v1"):
        r = run(["docker", "run", "--rm", "-e", "CHAOS_TOKEN=evaluator-only", img], base_env, timeout=120)
        msg = (r.stderr + r.stdout)
        check(f"startup.{img.split('/')[1].split(':')[0]}_refuses_default_token", f"{img} refuses the old default chaos token",
              r.returncode != 0 and "CHAOS_TOKEN" in msg, f"exit {r.returncode}")

    # 2. start
    api = Api(approval)
    if not a.no_up:
        services = [s for s in run(["docker", "compose", "config", "--services"], env).stdout.split() if s != "jaeger"]
        r = run(["docker", "compose", "up", "-d", "--force-recreate", *services], env, timeout=900)
        if r.returncode:
            check("startup.stack_up", "stack starts", False, r.stderr[-400:])
            return finish(out, a)
    st = wait_status(api)
    if not check("startup.brain_up", "brain answers /status", st is not None):
        return finish(out, a)
    time.sleep(45)   # let the rolling windows fill with healthy data
    r = run([sys.executable, "scripts/stock_gate.py", "--restock", "--force"], env, timeout=300)
    check("startup.stock", "inventory restocked and verified (scripts/stock_gate.py)", r.returncode == 0, r.stdout.strip()[-120:])

    # 3. bind addresses and rulebook
    names = run(["docker", "compose", "ps", "-q"], env).stdout.split()
    binds = []
    for cid in names:
        insp = json.loads(run(["docker", "inspect", cid], env).stdout)[0]
        for port, bs in (insp["HostConfig"].get("PortBindings") or {}).items():
            binds += [(insp["Name"].lstrip("/"), port, b.get("HostIp")) for b in bs or []]
    check("net.ports_localhost", "every published port is bound to 127.0.0.1", binds and all(ip == "127.0.0.1" for *_, ip in binds),
          [f"{n} {p} -> {ip}" for n, p, ip in binds])
    st = api.get("/status").json()
    pol = st.get("policy") or {}
    out["status_policy"] = pol
    check("policy.default_rulebook", "brain runs the plan rulebook (default.yaml: auto low only, payments protected, 10/h, 40 s)",
          pol.get("file") == "default.yaml" and pol.get("auto_allowed_risks") == ["low"] and pol.get("protected_services") == ["payments"]
          and pol.get("max_actions_per_hour") == 10 and pol.get("cooldown_s") == 40 and st.get("mode") == "autopilot",
          {"file": pol.get("file"), "mode": st.get("mode")})

    # 4. fault start needs the token
    codes = {"brain /challenge/start, no token": httpx.post(f"{EAI}/challenge/start", timeout=10).status_code,
             "evaluator /runs, no token": httpx.post(f"{EV}/runs", json={}, timeout=10).status_code,
             "evaluator /runs, wrong token": httpx.post(f"{EV}/runs", json={}, timeout=10,
                                                        headers={"X-Approval-Token": "wrong"}).status_code}
    check("net.fault_start_needs_token", "starting a fault without or with a wrong token is refused (403)",
          all(c == 403 for c in codes.values()), codes)

    # 5. kill switch round trip
    k_on = api.post("/killswitch", json={"on": True}).json()
    leave = api.post("/mode", json={"mode": "autopilot"}).status_code
    k_off = api.post("/killswitch", json={"on": False}).json()
    back = api.post("/mode", json={"mode": "autopilot"}).status_code
    check("policy.killswitch_roundtrip", "kill switch on -> watch-only; leaving watch-only refused (409); off; autopilot again",
          k_on.get("mode") == "watch-only" and leave == 409 and k_off.get("kill_switch") is False and back == 200,
          {"on": k_on, "leave_http": leave, "off": k_off, "back_http": back})

    # 6-8. scenarios with the latency probe running
    probe = LatencyProbe()
    probe.start()
    t_runs = time.time()
    for fn in (scenario_autopilot_low, scenario_protected, scenario_killswitch, scenario_high_risk):
        try:
            fn(api, out)
        except Exception as e:  # a failed scenario is a FAIL, not a crash of the whole check
            check(f"live.{fn.__name__}", "scenario ran", False, f"{type(e).__name__}: {e}")
    probe.stop_ev.set()
    lat = sorted(probe.lat)
    p95 = lat[int(0.95 * (len(lat) - 1))] if lat else None
    out["approvals_latency"] = {"n": len(lat), "p50_s": lat[len(lat) // 2] if lat else None, "p95_s": p95,
                                "max_s": lat[-1] if lat else None, "errors": probe.errors}
    check("lock.approvals_fast_live", "GET /approvals during the four runs: p95 under 0.2 s, no errors",
          bool(lat) and p95 < 0.2 and probe.errors == 0, {k: (round(v, 4) if isinstance(v, float) else v)
                                                          for k, v in out["approvals_latency"].items()})
    aud = audit_since(api, t_runs)
    acts = [x for x in aud if "ok" in x]
    ver = [x for x in aud if x.get("kind") == "verification"]
    check("audit.reason_and_verification", "audit records carry the policy reason; verification results are audited",
          bool(acts) and all(x.get("reason") for x in acts) and len(ver) >= len([x for x in acts if x.get("ok")]),
          {"actions": [(x["runbook"], x["service"], x["actor"], x.get("reason")) for x in acts],
           "verifications": [(x["service"], x["outcome"]) for x in ver]})

    # 9. Prometheus outage
    api.post("/mode", json={"mode": "watch-only"})
    before = {i["id"] for i in api.get("/incidents").json()}
    run(["docker", "compose", "stop", "prometheus"], env)
    time.sleep(16)
    st1 = api.get("/status").json()
    time.sleep(8)
    st2 = api.get("/status").json()
    new = [i["id"] for i in api.get("/incidents").json() if i["id"] not in before]
    run(["docker", "compose", "start", "prometheus"], env)
    failed = st2.get("telemetry_failed") or {}
    check("telemetry.prometheus_outage", "Prometheus stopped: brain keeps answering, reports the failed queries, opens no incident",
          bool(failed) and all("up" in v for v in failed.values()) and not new and st1.get("open_incidents", 0) == 0,
          {"failed_services": sorted(failed), "new_incidents": new, "last_error": st2.get("last_error")})
    for _ in range(30):
        time.sleep(3)
        if not (api.get("/status").json().get("telemetry_failed") or {}):
            break
    check("telemetry.recovers", "after Prometheus is back the failed-query list empties",
          not (api.get("/status").json().get("telemetry_failed") or {}))
    out["finished"] = now_ist()
    return finish(out, a, env)


def finish(out, a, env=None):
    out["checks"] = checks
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")
    n_pass = sum(c["result"] == "PASS" for c in checks)
    lines = [f"# Phase 1 live check (generated by `scripts/live_check_phase1.py`)", "",
             f"- Commit: `{out.get('commit')}`; started {out.get('started')}, finished {out.get('finished', 'not finished')}.",
             "- Stack: Docker Compose, telemetry condition T3 (no Jaeger), autopilot, rulebook `eternalai/rulebooks/default.yaml`.",
             "- Tokens: a throwaway approval token and chaos token generated by the script, passed through the environment only.",
             f"- Result: **{n_pass} of {len(checks)} checks passed.** Raw record: `results/live-checks/phase1.json`.", "",
             "| check | what | result | detail |", "|---|---|---|---|"]
    for c in checks:
        d = json.dumps(c["detail"], default=str) if not isinstance(c["detail"], str) else c["detail"]
        lines.append(f"| `{c['id']}` | {c['what']} | {c['result']} | {d.replace('|', '/')[:600]} |")
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{n_pass}/{len(checks)} passed; wrote {OUT_MD.relative_to(ROOT)}")
    if env is not None and not a.keep_running:
        run(["docker", "compose", "stop"], env)
    return 0 if n_pass == len(checks) else 1


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import stack_lock
    _commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    stack_lock.take("main", "Phase 1 live check", f"plan-complete@{_commit}")
    try:
        _rc = main()
    finally:
        stack_lock.release("main", f"plan-complete@{_commit}")
    sys.exit(_rc)
