"""Live demo rehearsal on a pinned checkout (tag demo-stable-1), same stack as the demo. Never approves anything itself.

    python tools/demo_rehearsal_ds1.py --checkout D:\\eAI\\eAI-demo-stable-1 --token-file D:\\eAI\\rehearsal-20261024\\approval.token

1. crash on web -> autopilot restart: detection time, action, verified healthy.
2. disk fill on web -> autopilot clear_temp_path; FAIL (and stop before step 3) if any other action ran without approval.
3. bad deploy on payments in ask-first: waits for a PERSON to approve in the dashboard (http://127.0.0.1:8050). The
   approval token is generated for this run and written only to --token-file (outside git; deleted at the end); it is
   never printed. Records the approver and the wait from proposal to approved execution.
Takes the shared Docker lock atomically (tools/stack_lock.py of this repo), stops the stack and releases its own lock
in a finally. Hard stop: --stop-by (IST, HH:MM). Results: docs/results/demo_rehearsal_<stamp>.md and
results/live-checks/demo_rehearsal_<stamp>.json in THIS repo, with the JSON's SHA256 in the report.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(HERE))
import stack_lock  # noqa: E402  (this repo's atomic lock)

IST = timezone(timedelta(hours=5, minutes=30))


def ist(t=None):
    return datetime.fromtimestamp(t or time.time(), IST).strftime("%Y-%m-%d %H:%M:%S IST")


def say(msg):
    print(f"{ist()} {msg}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkout", required=True)
    ap.add_argument("--token-file", required=True)
    ap.add_argument("--stop-by", default="19:35")
    ap.add_argument("--min-free-gb", type=float, default=3.0)
    ap.add_argument("--steps", default="1,2,3", help="subset of 1,2,3 (a fresh stack starts with the kill switch off)")
    ap.add_argument("--compose-override", default="", help="extra compose file (outside git), e.g. the demo's 300 s approval window")
    ap.add_argument("--note", default="", help="one line written into the evidence")
    a = ap.parse_args()
    steps = {s.strip() for s in a.steps.split(",") if s.strip()}
    ck = Path(a.checkout)
    sys.path.insert(0, str(ck / "scripts"))
    import live_check_phase1 as lc  # the checkout's helpers: run() and the API calls use the checkout's compose files
    import memguard
    h, m = map(int, a.stop_by.split(":"))
    stop_at = datetime.now(IST).replace(hour=h, minute=m, second=0, microsecond=0).timestamp()
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ck, capture_output=True, text=True).stdout.strip()
    tag = subprocess.run(["git", "describe", "--tags", "--exact-match"], cwd=ck, capture_output=True, text=True).stdout.strip()
    stamp = datetime.now(IST).strftime("%Y%m%d-%H%M")
    out = {"kind": "demo rehearsal (not a gate, not a benchmark)", "checkout": str(ck), "commit": commit, "tag": tag,
           "started": ist(), "steps": {}, "free_gb_at_start": round(memguard.free_ram_gb(), 2),
           "approval_ttl_s": "brain default (ETERNALAI_APPROVAL_TTL_S is not passed by this commit's compose file)",
           "compose_override": a.compose_override or None, "note": a.note or None}
    if out["free_gb_at_start"] < a.min_free_gb:
        say(f"STOP: only {out['free_gb_at_start']} GB free (< {a.min_free_gb})")
        return
    approval, chaos = secrets.token_urlsafe(24), secrets.token_urlsafe(24)
    tf = Path(a.token_file)
    tf.parent.mkdir(parents=True, exist_ok=True)
    tf.write_text(approval, encoding="utf-8")
    base = {k: v for k, v in os.environ.items() if k not in ("CHAOS_TOKEN", "ETERNALAI_APPROVAL_TOKEN")}
    env = {**base, "ETERNALAI_APPROVAL_TOKEN": approval, "CHAOS_TOKEN": chaos, "EAI_EVALUATOR_TOKEN": approval,
           "OTEL_SDK_DISABLED": "true", "ETERNALAI_MODE": "autopilot", "ETERNALAI_POLICY_FILE": "",
           "GEMINI_API_KEY": "", "GROQ_API_KEY": ""}
    stack_lock.take("main", f"demo rehearsal on {tag or commit}", f"{tag or 'pinned'}@{commit}")
    api = lc.Api(approval)
    try:
        say("building images from the checkout (docker compose --profile releases build)")
        b = lc.run(["docker", "compose", "--profile", "releases", "build"], env, timeout=2400)
        out["build_exit"] = b.returncode
        if b.returncode:
            out["build_tail"] = b.stderr[-600:]
            return
        services = [s for s in lc.run(["docker", "compose", "config", "--services"], env).stdout.split() if s != "jaeger"]
        files = ["-f", "docker-compose.yml"] + (["-f", a.compose_override] if a.compose_override else [])
        up = lc.run(["docker", "compose", *files, "up", "-d", "--force-recreate", *services], env, timeout=900)
        out["up_exit"] = up.returncode
        if up.returncode or lc.wait_status(api) is None:
            out["up_tail"] = up.stderr[-600:]
            return
        st = api.get("/status").json()
        out["status"] = {"mode": st.get("mode"), "policy_file": (st.get("policy") or {}).get("file"),
                         "auto_allowed_risks": (st.get("policy") or {}).get("auto_allowed_risks"),
                         "protected": (st.get("policy") or {}).get("protected_services")}
        ttl = lc.run(["docker", "compose", "exec", "-T", "eternalai", "printenv", "ETERNALAI_APPROVAL_TTL_S"], env).stdout.strip()
        if ttl:
            out["approval_ttl_s"] = f"{ttl} s (demo override {a.compose_override}, no code change)"
        out["free_gb_stack_up"] = round(memguard.free_ram_gb(), 2)
        say(f"stack up: {out['status']}; approval window {out['approval_ttl_s']}; free RAM {out['free_gb_stack_up']} GB; "
            "dashboard http://127.0.0.1:8050")
        time.sleep(45)
        r = lc.run([sys.executable, "tools/stock_gate.py", "--restock", "--force"], env, timeout=300)
        out["restock_exit"] = r.returncode

        def one(scenario, target, timeout_s=150, on_tick=None):
            t0 = time.time()
            rid = lc.start_run(api, scenario, target, timeout_s=timeout_s)
            say(f"{scenario} on {target}: run {rid} started")
            rev = lc.wait_run(api, rid, on_tick=on_tick, limit_s=max(60, stop_at - time.time()))
            t_inj = (rev.get("truth") or {}).get("t_inject", t0)
            incs = [i for i in api.get("/incidents").json() if i["opened_t"] >= t_inj - 1]
            audit = [x for x in api.get("/audit").json() if x.get("t", 0) >= t_inj]
            sc = rev.get("score") or {}
            return {"run_id": rid, "t_inject": ist(t_inj), "detected": sc.get("detected"),
                    "time_to_detect_s": sc.get("time_to_detect_s"), "recovered": sc.get("recovered"),
                    "time_to_verified_recovery_s": sc.get("time_to_verified_recovery_s"),
                    "failed_request_pct": sc.get("failed_request_pct"),
                    "incidents": [{"id": i["id"], "status": i["status"], "cause": i["likely_cause"], "services": i["services"],
                                   "verification": (i.get("verification") or {}).get("outcome"),
                                   "actions": [{k: x.get(k) for k in ("runbook_id", "service", "verdict", "risk", "reason",
                                                                      "executed", "approved_by", "t", "executed_t")}
                                               for x in i.get("actions", [])]} for i in incs],
                    "audit": [{k: x.get(k) for k in ("t", "runbook", "service", "actor", "ok")} for x in audit]}

        out["steps_requested"] = sorted(steps)

        def guard(name, mode):
            """Stop cleanly if the kill switch was turned on (only POST /killswitch with the token can do that)."""
            s = api.get("/status").json()
            out.setdefault("state_before_step", {})[name] = {"mode": s.get("mode"), "kill_switch": s.get("kill_switch")}
            if s.get("kill_switch"):
                say(f"STOP before {name}: kill switch is ON (set outside this script); nothing more is run")
                return False
            if mode and s.get("mode") not in {mode, {"ask-first": "ask", "autopilot": "autopilot"}[mode]}:
                say(f"STOP before {name}: mode is {s.get('mode')}, expected {mode}")
                return False
            return True

        # 1. crash -> autopilot restart
        if "1" in steps:
            if not guard("1", "autopilot"):
                return
            s1 = one("crash", "web")
            ex = [x for i in s1["incidents"] for x in i["actions"] if x["executed"]]
            s1["result"] = "PASS" if (s1["detected"] and any(x["runbook_id"] == "restart_service" and x["approved_by"] is None
                                                             for x in ex) and s1["recovered"]) else "FAIL"
            out["steps"]["1_crash_autopilot"] = s1
            say(f"step 1: {s1['result']} (detect {s1['time_to_detect_s']} s, recovered {s1['recovered']})")
            time.sleep(20)

        # 2. disk fill -> autopilot clear_temp_path, and nothing else without approval
        if "2" not in steps:
            others = []
        elif not guard("2", "autopilot"):
            return
        if "2" in steps:
            s2 = one("disk_fill", "web")
            ex = [x for i in s2["incidents"] for x in i["actions"] if x["executed"]]
            others = [x for x in ex if x["runbook_id"] != "clear_temp_path" and not x["approved_by"]]
            others += [x for x in s2["audit"] if x.get("actor") == "autopilot" and x.get("runbook") != "clear_temp_path"]
            s2["other_actions_without_approval"] = others
            s2["result"] = "PASS" if (any(x["runbook_id"] == "clear_temp_path" for x in ex) and not others
                                      and s2["recovered"]) else "FAIL"
            out["steps"]["2_disk_autopilot"] = s2
            say(f"step 2: {s2['result']} (other actions without approval: {len(others)})")
            if others:
                say("STOP: disk fill ran another action without approval; step 3 not run")
                return
            time.sleep(20)
        if "3" not in steps:
            return

        # 3. bad deploy on payments, ask-first, a person approves in the dashboard
        out["mode_switch_http"] = api.post("/mode", json={"mode": "ask-first"}).status_code
        if not guard("3", "ask-first"):
            return
        seen = {}

        def tick(_st):
            if "pending" in seen:
                return
            try:
                pend = [p for p in api.get("/approvals").json() if p.get("service") == "payments"]
            except Exception:  # noqa: BLE001
                return
            if pend:
                seen["pending"] = {"t": time.time(), "incident_id": pend[0].get("incident_id"),
                                   "runbook": pend[0].get("runbook_id"), "free_gb": round(memguard.free_ram_gb(), 2)}
                say(f"PENDING APPROVAL: {pend[0].get('runbook_id')} on payments (incident {pend[0].get('incident_id')}). "
                    "Approve it in the dashboard http://127.0.0.1:8050 (token from the token file).")

        s3 = one("bad_deploy", "payments", timeout_s=600, on_tick=tick)
        acts = [x for i in s3["incidents"] for x in i["actions"]]
        appr = next((x for x in acts if x.get("approved_by") and x.get("executed")), None)
        s3["pending"] = {**seen.get("pending", {}), "t": ist(seen["pending"]["t"])} if "pending" in seen else None
        s3["approver_recorded"] = appr["approved_by"] if appr else None
        s3["wait_proposal_to_execution_s"] = round(appr["executed_t"] - appr["t"], 1) if appr and appr.get("executed_t") else None
        pre = [x for x in acts if x.get("executed") and not x.get("approved_by")]
        s3["executed_without_approval"] = pre
        s3["result"] = "PASS" if (appr and not pre and s3["recovered"]) else ("NOT APPROVED" if not appr else "FAIL")
        out["steps"]["3_bad_deploy_ask_first"] = s3
        say(f"step 3: {s3['result']} (approver {s3['approver_recorded']}, wait {s3['wait_proposal_to_execution_s']} s)")
    finally:
        lc.run(["docker", "compose", "stop"], env, timeout=300)
        stack_lock.release("main", f"{tag or 'pinned'}@{commit}")
        tf.unlink(missing_ok=True)
        out["finished"] = ist()
        write(out, stamp)
        say("stack stopped, lock released, token file deleted")


def write(out, stamp):
    j = REPO / "results" / "live-checks" / f"demo_rehearsal_{stamp}.json"
    md = REPO / "docs" / "results" / f"demo_rehearsal_{stamp}.md"
    j.parent.mkdir(parents=True, exist_ok=True)
    j.write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")
    sha = hashlib.sha256(j.read_bytes()).hexdigest()
    L = [f"# Demo rehearsal on `{out.get('tag') or out['commit']}` (`{out['commit']}`) (generated by `tools/demo_rehearsal_ds1.py`)", "",
         f"- {out['kind']}. Started {out['started']}, finished {out.get('finished')}. Free RAM at start {out['free_gb_at_start']} GB.",
         f"- Brain: {out.get('status')}. Approval window: {out['approval_ttl_s']}. Free RAM with the stack up: "
         f"{out.get('free_gb_stack_up')} GB.", *([f"- Note: {out['note']}"] if out.get("note") else []),
         f"- Raw record: `results/live-checks/{j.name}` (SHA256 `{sha}`).", "",
         "| step | result | detection s | action(s) executed | approved by | verified | failed-request % |", "|---|---|---|---|---|---|---|"]
    for k, s in out["steps"].items():
        ex = [f"{x['runbook_id']}@{x['service']}" for i in s["incidents"] for x in i["actions"] if x["executed"]]
        ap = sorted({str(x['approved_by']) for i in s["incidents"] for x in i["actions"] if x["executed"]})
        ver = [i["verification"] for i in s["incidents"]]
        L.append(f"| {k} | {s['result']} | {s['time_to_detect_s']} | {', '.join(ex) or '-'} | {', '.join(ap) or '-'} | "
                 f"{', '.join(map(str, ver)) or '-'} | {s['failed_request_pct']} |")
    s3 = out["steps"].get("3_bad_deploy_ask_first")
    if s3:
        L += ["", f"Step 3: pending at {(s3.get('pending') or {}).get('t')}; approver recorded by the brain: "
                  f"`{s3['approver_recorded']}` (this commit's dashboard sends the fixed name `dashboard`); wait from proposal "
                  f"to approved execution {s3['wait_proposal_to_execution_s']} s."]
    md.write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
