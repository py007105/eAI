"""Controlled integration checks for the release gate (docs/RELEASE_GATE.md, items G4-G6), on the real Compose stack.

    python scripts/live_check_controlled.py

"Controlled" means a deliberate substitution makes a condition occur that the scripted faults did not produce on their
own. Each substitution is made INSIDE the running brain container (docker exec) and the brain container is restarted;
code and image are the candidate's, unchanged. After each check the brain container is recreated fresh from the image.
These checks show that the integration path works on the candidate. They are NOT evidence that the condition occurs
naturally, nor evidence of generalisation.

  K1  knowledge base loaded; GET /kb/{label} for the six live labels; fix_ranking on every diagnosed incident and the
      proposal equal to its first executable entry (all incidents seen in this script)
  C1  root margin substituted with 1.01 (above every possible gap) -> crash on web -> abstain "two close root candidates",
      nothing executed
  C2  learned limits substituted with empty limits -> disk_fill on web (then error_spike on web if no forest-only
      incident occurred) -> an incident with anomaly_source forest_only gets needs_approval, nothing auto-executed;
      if no forest-only incident occurs, C2 is reported NOT MET
  K2  outcomes file substituted without the memory_leak/recreate_container rows -> memory_leak on web -> the proposal
      follows the re-ranked list (expected: rollback_release, high risk, waits for approval), nothing executed
Takes the Docker lock (parent mode inside scripts/run_v3_sequence.py). Throwaway tokens through the environment only.
"""
from __future__ import annotations

import json
import os
import secrets
import subprocess
import sys
import time
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
check, checks = lc.check, lc.checks

SUB_MARGIN = ("import json; p='/srv/models/artifacts/root_margin.json'; d=json.load(open(p)); d['margin']=1.01; "
              "d['controlled_check']='substituted at run time'; json.dump(d, open(p,'w'))")
SUB_LIMITS = ("import joblib; p='/srv/models/artifacts/detectors.joblib'; d=joblib.load(p); "
              "[setattr(v,'limits',{}) for v in d.values()]; joblib.dump(d,p); print(len(d))")
SUB_OUTCOMES = ("import pandas as pd; p='/srv/data/kb/outcomes_measured.csv'; m=pd.read_csv(p); "
                "m=m[~((m.live_label=='memory_leak')&(m.fix=='recreate_container'))]; m.to_csv(p,index=False); print(len(m))")


def brain_exec(code, env):
    return lc.run(["docker", "exec", BRAIN, "python", "-c", code], env, timeout=120)


def restart_brain(api, env):
    lc.run(["docker", "restart", BRAIN], env, timeout=120)
    ok = lc.wait_status(api) is not None
    time.sleep(45)                   # let the rolling windows fill with healthy data
    return ok


def fresh_brain(api, env):
    lc.run(["docker", "compose", "up", "-d", "--force-recreate", "--no-deps", "eternalai"], env, timeout=300)
    ok = lc.wait_status(api) is not None
    time.sleep(45)
    return ok


def executed(run):
    return [(a.get("runbook"), a.get("service"), a.get("actor")) for a in run["audit"] if a.get("ok")]


def summary(incs):
    return [{"id": i["id"], "status": i["status"], "cause": i["likely_cause"], "abstained": i["abstained"],
             "source": (i.get("diagnosis") or {}).get("anomaly_source"), "gap": (i.get("diagnosis") or {}).get("root_gap"),
             "reason": (i.get("diagnosis") or {}).get("abstain_reason"),
             "actions": [(a.get("runbook_id"), a.get("service"), a.get("verdict"), a.get("executed")) for a in i.get("actions") or []]}
            for i in incs]


def main():
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    approval, chaos = secrets.token_urlsafe(24), secrets.token_urlsafe(24)
    base = {k: v for k, v in os.environ.items() if k not in ("CHAOS_TOKEN", "ETERNALAI_APPROVAL_TOKEN")}
    env = {**base, "ETERNALAI_APPROVAL_TOKEN": approval, "CHAOS_TOKEN": chaos, "EAI_EVALUATOR_TOKEN": approval,
           "OTEL_SDK_DISABLED": "true", "ETERNALAI_MODE": "autopilot", "ETERNALAI_POLICY_FILE": ""}
    out = {"commit": commit, "started": lc.now_ist(), "spec": "docs/RELEASE_GATE.md G4-G6"}
    all_incs = []
    stack_lock.take("main", "controlled checks", f"plan-complete@{commit}")
    try:
        out["free_gb_at_start"] = round(p4.wait_memory(), 2)
        services = [s for s in lc.run(["docker", "compose", "config", "--services"], env).stdout.split() if s != "jaeger"]
        if lc.run(["docker", "compose", "up", "-d", "--force-recreate", *services], env, timeout=900).returncode:
            check("setup.stack_up", "stack starts", False)
            return
        api = lc.Api(approval)
        if not check("setup.brain_up", "brain answers /status", lc.wait_status(api) is not None):
            return
        time.sleep(45)
        lc.run([sys.executable, "scripts/stock_gate.py", "--restock", "--force"], env, timeout=300)

        # K1 (part 1): KB loaded and served
        st = api.get("/status").json()
        kbs = st.get("knowledge_base") or {}
        kb_ok = {lab: api.get(f"/kb/{lab}") for lab in LABELS}
        kb_det = {lab: (r.status_code, bool(r.status_code == 200 and r.json().get("entry")),
                        len(r.json().get("ranked_fixes", [])) if r.status_code == 200 else 0) for lab, r in kb_ok.items()}
        out["k1_kb"] = {"status": kbs, "kb": kb_det}

        # C1: close candidates -> abstain
        sub = brain_exec(SUB_MARGIN, env)
        restarted = restart_brain(api, env)
        margin_now = api.get("/status").json().get("root_margin")
        r1 = p4.run_scenario(api, "crash", "web")
        all_incs += r1["incidents"]
        diag1 = [i for i in r1["incidents"] if i.get("diagnosis")]
        close = [i for i in diag1 if "two close root candidates" in ((i["diagnosis"] or {}).get("abstain_reason") or "")]
        check("C1", "controlled: margin substituted (1.01) -> crash on web abstains 'two close root candidates'; nothing executed",
              sub.returncode == 0 and restarted and margin_now == 1.01 and bool(close) and not executed(r1)
              and all(not a.get("executed") for i in close for a in i.get("actions") or []),
              {"margin_now": margin_now, "incidents": summary(r1["incidents"]), "executed": executed(r1)})
        fresh_brain(api, env)

        # C2: forest-only -> approval
        sub = brain_exec(SUB_LIMITS, env)
        restart_brain(api, env)
        c2_runs, forest = [], []
        for scen in ("disk_fill", "error_spike"):
            r = p4.run_scenario(api, scen, "web")
            all_incs += r["incidents"]
            c2_runs.append({"scenario": scen, "incidents": summary(r["incidents"]), "executed": executed(r)})
            forest += [(i, r) for i in r["incidents"] if (i.get("diagnosis") or {}).get("anomaly_source") == "forest_only"]
            if forest:
                break
        auto = [a for i, _ in forest for a in i.get("actions") or [] if a.get("verdict") == "execute"]
        approval_ok = all(any(a.get("verdict") in ("needs_approval", "expired_unapproved") for a in i.get("actions") or [])
                          or not i.get("actions") for i, _ in forest)
        check("C2", "controlled: learned limits substituted (empty) -> a forest-only incident gets needs_approval; nothing auto-executed"
              + ("" if forest else " [NOT MET: no forest-only incident occurred]"),
              sub.returncode == 0 and bool(forest) and not auto and approval_ok
              and not [x for x in (e for c in c2_runs for e in c["executed"]) if x[2] == "autopilot"],
              {"limits_substituted_for_services": sub.stdout.strip(), "runs": c2_runs, "forest_only_incidents": len(forest)})
        fresh_brain(api, env)

        # K2: controlled re-ranking drives the proposal
        sub = brain_exec(SUB_OUTCOMES, env)
        restart_brain(api, env)
        ranked = api.get("/kb/memory_leak").json().get("ranked_fixes", [])
        first_exec = next((f["runbook_id"] for f in ranked if f.get("runbook_id")), None)
        r3 = p4.run_scenario(api, "memory_leak", "web")
        all_incs += r3["incidents"]
        ml = [i for i in r3["incidents"] if i.get("likely_cause") == "memory_leak" and i.get("actions")]
        prop = ml[0]["actions"][0] if ml else {}
        check("K2", "controlled: outcomes substituted (no memory_leak/recreate rows) -> the proposal follows the re-ranked list; "
              "it waits if high risk; nothing executed without approval",
              sub.returncode == 0 and first_exec is not None and first_exec != "recreate_container" and bool(ml)
              and prop.get("runbook_id") == first_exec
              and (prop.get("risk") != "high" or prop.get("verdict") == "needs_approval")
              and not [x for x in executed(r3) if x[2] == "autopilot" and prop.get("risk") == "high"],
              {"rows_left": sub.stdout.strip(), "re_ranked_first": first_exec, "proposal": prop,
               "incidents": summary(r3["incidents"]), "executed": executed(r3)})
        fresh_brain(api, env)

        # K1 (part 2): every diagnosed incident of this script carries fix_ranking and proposes its first executable entry
        diag = [i for i in all_incs if i.get("diagnosis") and not i.get("abstained") and i.get("actions")]
        bad = []
        for i in diag:
            fr = (i["diagnosis"] or {}).get("fix_ranking") or []
            first = next((f["runbook_id"] for f in fr if f.get("runbook_id")), None)
            if not fr or i["actions"][0].get("runbook_id") != first:
                bad.append(i["id"])
        check("K1", "KB loaded; GET /kb answers for the six live labels; every proposing incident carries fix_ranking and "
              "proposes its first executable entry",
              kbs.get("faults") == 17 and all(v[0] == 200 and v[1] and v[2] > 0 for v in kb_det.values()) and bool(diag) and not bad,
              {"kb": kb_det, "proposing_incidents": len(diag), "mismatches": bad})
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
    lines = ["# Controlled integration checks (generated by `scripts/live_check_controlled.py`)", "",
             "- Gate items G4-G6 of `docs/RELEASE_GATE.md` (written before the run).",
             f"- Commit and image: `{out.get('commit')}`; started {out.get('started')}, finished {out.get('finished', 'not finished')}.",
             "- **Controlled checks:** each condition was produced by a deliberate substitution inside the running brain container "
             "(then restarted; recreated fresh afterwards). They show the integration path works on this build; they are not "
             "evidence that the condition occurs naturally or of generalisation.",
             f"- Result: **{n} of {len(checks)} checks passed.** Raw record: `results/live-checks/controlled.json`.", "",
             "| check | what | result | detail |", "|---|---|---|---|"]
    for c in checks:
        d = c["detail"] if isinstance(c["detail"], str) else json.dumps(c["detail"], default=str)
        lines.append(f"| `{c['id']}` | {c['what']} | {c['result']} | {d.replace('|', '/')[:900]} |")
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{n}/{len(checks)} passed; wrote {OUT_MD.relative_to(ROOT)}", flush=True)


if __name__ == "__main__":
    main()
