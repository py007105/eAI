"""Controlled integration checks for the release gate (docs/RELEASE_GATE.md, items G4-G6), on the real Compose stack.

    python scripts/live_check_controlled.py

WHAT IS AND IS NOT CHANGED
- The image and every source file are unchanged.
- For each controlled check one DATA file is replaced in the running brain container's writable layer (docker exec), and
  the brain container is restarted so that it loads it. During that check the brain therefore runs a MODIFIED RUNTIME
  CONFIGURATION, not the candidate's:
    C1  models/artifacts/root_margin.json      margin 0.1215 -> 1.01   (every real gap is then below the margin)
    C2  models/artifacts/detectors.joblib      learned limits emptied  (only "down" or the joint forest score can flag)
    K2  data/kb/outcomes_measured.csv          memory_leak/recreate_container rows removed (changes that ranking)
- The decision code under test (ranker gap test, anomaly_source, policy, executor) runs unmodified; nothing forces the
  expected output. The expected behaviour must come out of the real path after a real injected fault.
- After EVERY check, in a `finally`, the brain container is recreated from the image, and the restoration is VERIFIED:
  SHA256 of the three files inside the container must equal the files of this commit, and /status must show margin
  0.121529. The script ends with S1, an unmodified-stack smoke check (crash on web -> autopilot restart executed).
- "No unauthorized action" is checked from two sources: the executor's audit records (every attempt is audited) and
  Docker's own event log for the target container between injection and the end of the run (restart/start/create/
  exec_start would show an action).

Statuses: PASS, FAIL, or INCOMPLETE (the condition under test did not occur, e.g. no forest-only incident in C2;
INCOMPLETE is never a pass). Every output carries the execution ID (EAI_EXEC_ID from scripts/run_v3_sequence.py).
These are controlled checks: they show the integration path works on the candidate's code; they are not evidence that
the conditions occur naturally, nor evidence of generalisation.
"""
from __future__ import annotations

import hashlib
import json
import os
import secrets
import subprocess
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import live_check_phase1 as lc  # noqa: E402
import live_check_phase4a as p4  # noqa: E402
import stack_lock  # noqa: E402

ROOT = lc.ROOT
OUT_MD = ROOT / "docs" / "results" / "live_check_controlled.md"
OUT_JSON = ROOT / "results" / "live-checks" / "controlled.json"
BRAIN = "eai-eternalai-1"
LABELS = ["down", "memory_leak", "disk_fill", "bad_deploy", "error_spike", "latency_spike"]
FILES = {"models/artifacts/root_margin.json": "/srv/models/artifacts/root_margin.json",
         "models/artifacts/detectors.joblib": "/srv/models/artifacts/detectors.joblib",
         "data/kb/outcomes_measured.csv": "/srv/data/kb/outcomes_measured.csv"}
SUBSTITUTIONS = {
    "C1": ("models/artifacts/root_margin.json", "margin 0.1215 -> 1.01",
           "import json; p='/srv/models/artifacts/root_margin.json'; d=json.load(open(p)); d['margin']=1.01; json.dump(d, open(p,'w'))"),
    "C2": ("models/artifacts/detectors.joblib", "learned limits emptied for every service",
           "import joblib; p='/srv/models/artifacts/detectors.joblib'; d=joblib.load(p); "
           "[setattr(v,'limits',{}) for v in d.values()]; joblib.dump(d,p); print(len(d))"),
    "K2": ("data/kb/outcomes_measured.csv", "memory_leak / recreate_container rows removed",
           "import pandas as pd; p='/srv/data/kb/outcomes_measured.csv'; m=pd.read_csv(p); "
           "m=m[~((m.live_label=='memory_leak')&(m.fix=='recreate_container'))]; m.to_csv(p,index=False); print(len(m))"),
}
ACTION_EVENTS = {"restart", "start", "create", "exec_start", "exec_create"}
check, checks = lc.check, lc.checks
EXEC_ID = os.environ.get("EAI_EXEC_ID") or f"manual-{uuid.uuid4().hex[:8]}"


def status_line(cid, what, status, detail):
    """Like lc.check but with the third status INCOMPLETE."""
    checks.append({"id": cid, "what": what, "result": status, "detail": detail, "t": lc.now_ist()})
    print(f"[{status}] {cid}: {what} - {detail}", flush=True)


def brain_exec(code, env):
    return lc.run(["docker", "exec", BRAIN, "python", "-c", code], env, timeout=120)


def wait_brain(api):
    ok = lc.wait_status(api) is not None
    time.sleep(45)                   # let the rolling windows fill with healthy data
    return ok


def fresh_brain(api, env):
    lc.run(["docker", "compose", "up", "-d", "--force-recreate", "--no-deps", "eternalai"], env, timeout=300)
    return wait_brain(api)


def verify_restored(api, env) -> dict:
    expected = {rel: hashlib.sha256((ROOT / rel).read_bytes()).hexdigest() for rel in FILES}
    code = "import hashlib,json; print(json.dumps({p: hashlib.sha256(open(p,'rb').read()).hexdigest() for p in %r}))" % list(FILES.values())
    r = brain_exec(code, env)
    try:
        inside = json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        inside = {}
    same = {rel: inside.get(FILES[rel]) == h for rel, h in expected.items()}
    try:
        margin = api.get("/status").json().get("root_margin")
    except Exception:  # noqa: BLE001
        margin = None
    return {"files_equal_to_commit": same, "margin": margin,
            "restored": all(same.values()) and margin is not None and abs(margin - 0.121529) < 1e-6}


def docker_actions(target, t0, t1, env) -> list:
    r = lc.run(["docker", "events", "--since", str(int(t0)), "--until", str(int(t1) + 1), "--filter", f"container=eai-{target}-1",
                "--format", "{{.Action}}"], env, timeout=60)
    acts = [a.split(":")[0].strip() for a in r.stdout.split()]
    return [a for a in acts if a in ACTION_EVENTS]


def run_controlled(api, env, scenario, target):
    """A real evaluator run; then the executor's audit records and Docker's own events for the target container between the
    injection and the end of the run (before the evaluator's restore). The restore itself is outside that window."""
    t_start = time.time()
    r = p4.run_scenario(api, scenario, target)
    try:
        rev = api.get(f"/runs/{r['run_id']}/reveal", base=lc.EV).json()
        t0, t_end = rev["truth"]["t_inject"], rev["score"]["t_end"]
    except Exception:  # noqa: BLE001  (no reveal: use the whole run and say so)
        t0, t_end, r["window_note"] = t_start, time.time(), "reveal unavailable: window = whole run including restore"
    r["docker_actions_on_target"] = docker_actions(target, t0, t_end, env)
    r["audited_actions"] = [(a.get("runbook"), a.get("service"), a.get("actor")) for a in r["audit"] if "ok" in a]
    return r


def summary(incs):
    return [{"id": i["id"], "status": i["status"], "cause": i["likely_cause"], "abstained": i["abstained"],
             "source": (i.get("diagnosis") or {}).get("anomaly_source"), "gap": (i.get("diagnosis") or {}).get("root_gap"),
             "reason": (i.get("diagnosis") or {}).get("abstain_reason"),
             "actions": [(a.get("runbook_id"), a.get("service"), a.get("verdict"), a.get("executed")) for a in i.get("actions") or []]}
            for i in incs]


def controlled(cid, api, env, body, out):
    """Apply substitution `cid`, restart the brain, run `body`, and ALWAYS restore + verify afterwards."""
    rel, what, code = SUBSTITUTIONS[cid]
    rec = {"file": rel, "substitution": what}
    try:
        sub = brain_exec(code, env)
        rec["substitution_exit"] = sub.returncode
        lc.run(["docker", "restart", BRAIN], env, timeout=120)
        rec["brain_up_after_substitution"] = wait_brain(api)
        if sub.returncode == 0 and rec["brain_up_after_substitution"]:
            body(rec)
        else:
            status_line(cid, "substitution could not be applied", "FAIL", rec)
    finally:
        fresh_brain(api, env)
        rec["restoration"] = verify_restored(api, env)
        out.setdefault("controlled", {})[cid] = rec
        if not rec["restoration"]["restored"]:
            status_line(f"{cid}.restore", "brain restored to the candidate's files after the check", "FAIL", rec["restoration"])


def main():
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    approval, chaos = secrets.token_urlsafe(24), secrets.token_urlsafe(24)
    base = {k: v for k, v in os.environ.items() if k not in ("CHAOS_TOKEN", "ETERNALAI_APPROVAL_TOKEN")}
    env = {**base, "ETERNALAI_APPROVAL_TOKEN": approval, "CHAOS_TOKEN": chaos, "EAI_EVALUATOR_TOKEN": approval,
           "OTEL_SDK_DISABLED": "true", "ETERNALAI_MODE": "autopilot", "ETERNALAI_POLICY_FILE": ""}
    out = {"commit": commit, "execution_id": EXEC_ID, "started": lc.now_ist(), "spec": "docs/RELEASE_GATE.md G4-G6"}
    all_incs = []
    stack_lock.take("main", "controlled checks", f"plan-complete@{commit}")
    api = lc.Api(approval)
    try:
        out["free_gb_at_start"] = round(p4.wait_memory(), 2)
        services = [s for s in lc.run(["docker", "compose", "config", "--services"], env).stdout.split() if s != "jaeger"]
        if lc.run(["docker", "compose", "up", "-d", "--force-recreate", *services], env, timeout=900).returncode:
            check("setup.stack_up", "stack starts", False)
            return
        if not check("setup.brain_up", "brain answers /status", wait_brain(api)):
            return
        lc.run([sys.executable, "scripts/stock_gate.py", "--restock", "--force"], env, timeout=300)
        out["initial_state"] = verify_restored(api, env)
        check("setup.unmodified", "the brain starts with exactly this commit's files (SHA256) and margin 0.121529",
              out["initial_state"]["restored"], out["initial_state"])
        kb_status = api.get("/status").json().get("knowledge_base") or {}
        kb = {lab: api.get(f"/kb/{lab}") for lab in LABELS}
        kb_det = {lab: (r.status_code, bool(r.status_code == 200 and r.json().get("entry")),
                        len(r.json().get("ranked_fixes", [])) if r.status_code == 200 else 0) for lab, r in kb.items()}

        def c1(rec):
            margin_now = api.get("/status").json().get("root_margin")
            r = run_controlled(api, env, "crash", "web")
            all_incs.extend(r["incidents"])
            close = [i for i in r["incidents"] if "two close root candidates" in (((i.get("diagnosis") or {}).get("abstain_reason")) or "")]
            rec.update(margin_in_brain=margin_now, incidents=summary(r["incidents"]), audited_actions=r["audited_actions"],
                       docker_actions_on_target=r["docker_actions_on_target"])
            if not close:
                status_line("C1", "controlled (modified runtime: margin 1.01): a real crash on web must abstain 'two close root "
                            "candidates'", "INCOMPLETE" if not r["incidents"] else "FAIL", rec)
                return
            ok = (margin_now == 1.01 and all(i["abstained"] and i["status"] == "escalated" and not i.get("actions") for i in close)
                  and not r["audited_actions"] and not r["docker_actions_on_target"])
            status_line("C1", "controlled (modified runtime: margin 1.01): a real crash on web abstains 'two close root "
                        "candidates'; no proposal; no audited action; no Docker action on web", "PASS" if ok else "FAIL", rec)

        def c2(rec):
            runs, forest = [], []
            for scen in ("disk_fill", "error_spike"):
                r = run_controlled(api, env, scen, "web")
                all_incs.extend(r["incidents"])
                runs.append({"scenario": scen, "incidents": summary(r["incidents"]), "audited_actions": r["audited_actions"],
                             "docker_actions_on_target": r["docker_actions_on_target"]})
                forest += [(i, r) for i in r["incidents"] if (i.get("diagnosis") or {}).get("anomaly_source") == "forest_only"]
                if forest:
                    break
            rec.update(runs=runs, forest_only_incidents=len(forest))
            if not forest:
                status_line("C2", "controlled (modified runtime: learned limits emptied): no forest-only incident occurred",
                            "INCOMPLETE", rec)
                return
            waited = all(i.get("actions") and i["actions"][0].get("verdict") in ("needs_approval", "expired_unapproved")
                         and "unusual combination" in (i["actions"][0].get("reason") or "") for i, _ in forest)
            unauthorised = [a for _, r in forest for a in r["audited_actions"] if a[2] == "autopilot"] + \
                           [a for _, r in forest for a in r["docker_actions_on_target"]]
            status_line("C2", "controlled (modified runtime: learned limits emptied): a forest-only incident waits for approval "
                        "('unusual combination'); no autopilot action audited; no Docker action on web",
                        "PASS" if waited and not unauthorised else "FAIL", {**rec, "unauthorised": unauthorised})

        def k2(rec):
            ranked = api.get("/kb/memory_leak").json().get("ranked_fixes", [])
            first = next((f["runbook_id"] for f in ranked if f.get("runbook_id")), None)
            r = run_controlled(api, env, "memory_leak", "web")
            all_incs.extend(r["incidents"])
            ml = [i for i in r["incidents"] if i.get("likely_cause") == "memory_leak" and i.get("actions")]
            prop = ml[0]["actions"][0] if ml else {}
            rec.update(re_ranked_first=first, proposal=prop, incidents=summary(r["incidents"]),
                       audited_actions=r["audited_actions"], docker_actions_on_target=r["docker_actions_on_target"])
            if not ml:
                status_line("K2", "controlled (modified runtime: outcomes file): no memory_leak proposal occurred", "INCOMPLETE", rec)
                return
            high = prop.get("risk") == "high"
            ok = (first not in (None, "recreate_container") and prop.get("runbook_id") == first
                  and (not high or (prop.get("verdict") in ("needs_approval", "expired_unapproved")
                                    and not r["audited_actions"] and not r["docker_actions_on_target"])))
            status_line("K2", "controlled (modified runtime: outcomes file): the proposal follows the re-ranked list; a high-risk "
                        "proposal waits; no audited or Docker action without approval", "PASS" if ok else "FAIL", rec)

        controlled("C1", api, env, c1, out)
        controlled("C2", api, env, c2, out)
        controlled("K2", api, env, k2, out)

        # S1: unmodified-stack smoke check after all restorations
        out["final_state"] = verify_restored(api, env)
        s = run_controlled(api, env, "crash", "web")
        all_incs.extend(s["incidents"])
        ok = out["final_state"]["restored"] and any(a[0] == "restart_service" and a[2] == "autopilot" for a in s["audited_actions"])
        check("S1", "unmodified stack after restoration: files equal this commit, margin 0.121529; a real crash on web is restarted "
              "by autopilot", ok, {"final_state": out["final_state"], "audited_actions": s["audited_actions"],
                                   "incidents": summary(s["incidents"])})

        # K1: the knowledge base on the unmodified candidate, and fix_ranking driving every proposal seen in this script
        proposing = [i for i in all_incs if i.get("diagnosis") and not i.get("abstained") and i.get("actions")]
        bad = []
        for i in proposing:
            fr = (i["diagnosis"] or {}).get("fix_ranking") or []
            first = next((f["runbook_id"] for f in fr if f.get("runbook_id")), None)
            if not fr or i["actions"][0].get("runbook_id") != first:
                bad.append(i["id"])
        check("K1", "KB loaded (17 faults); GET /kb answers for the six live labels; every proposing incident carries fix_ranking "
              "and proposes its first executable entry",
              kb_status.get("faults") == 17 and all(v[0] == 200 and v[1] and v[2] > 0 for v in kb_det.values())
              and bool(proposing) and not bad, {"kb": kb_det, "proposing_incidents": len(proposing), "mismatches": bad})
        out["finished"] = lc.now_ist()
    finally:
        try:
            fresh_brain(api, env)          # never leave a modified brain behind, even after an exception
            out["exit_state"] = verify_restored(api, env)
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
    lines = ["# Controlled integration checks (generated by `scripts/live_check_controlled.py`)", "",
             "- Gate items G4-G6 of `docs/RELEASE_GATE.md` (written before the run).",
             f"- Commit: `{out.get('commit')}`; execution ID: `{out.get('execution_id')}`; started {out.get('started')}, "
             f"finished {out.get('finished', 'not finished')}.",
             "- The image and all source files are unchanged. For C1, C2 and K2 one data file was replaced inside the running "
             "brain container (listed per check), so during those checks the brain ran a **modified runtime configuration**. "
             "After each, the container was recreated from the image and the restoration verified by SHA256; S1 is a smoke "
             "check on the restored, unmodified stack.",
             "- Controlled checks show that the integration path works on this code. They are not evidence that the conditions "
             "occur naturally, nor evidence of generalisation.",
             f"- Result: **{n} of {len(checks)} checks passed**; INCOMPLETE: {inc}. Raw record: `results/live-checks/controlled.json`.",
             "", "| check | what | result | detail |", "|---|---|---|---|"]
    for c in checks:
        d = c["detail"] if isinstance(c["detail"], str) else json.dumps(c["detail"], default=str)
        lines.append(f"| `{c['id']}` | {c['what']} | {c['result']} | {d.replace('|', '/')[:900]} |")
    lines += ["", "## Substitutions", "", "| check | file in the brain container | change |", "|---|---|---|"]
    lines += [f"| {k} | `{v[0]}` | {v[1]} |" for k, v in SUBSTITUTIONS.items()]
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{n}/{len(checks)} passed, {inc} incomplete; wrote {OUT_MD.relative_to(ROOT)}", flush=True)


if __name__ == "__main__":
    main()
