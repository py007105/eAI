"""Live check of the intended COMBINED deployment (all images built from this checkout), separate from the release candidate.

    python scripts/live_check_combined.py            # from a checkout pinned at the combined revision

This is not release-gate evidence for any candidate: it validates the integrated revision as deployed (the teammate
work plus the dashboard wiring), with every image built from this commit and the dashboard served by its own container.
  B1 every image builds from this commit (docker compose --profile releases build);
  B2 the brain starts unmodified (its three data files equal this commit's, SHA256; margin 0.121529);
  B3 smoke: a real crash on web is restarted by autopilot (audited restart_service by autopilot);
  B4 the dashboard CONTAINER (http://127.0.0.1:8050, built from this commit) passes scripts/live_check_dashboard_charts.py
     with --populated during a real latency fault on web (D1-D6; D6 = a non-empty explanation equal to the brain's live
     features). Report: docs/results/dashboard_charts_combined.md.
Building replaces the eai/* image tags with this commit's images: run it after any work that needs the candidate's images.
Takes the Docker lock atomically (or runs under a parent's lock) and releases only its own.
"""
from __future__ import annotations

import json
import os
import secrets
import subprocess
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import live_check_controlled as cc  # noqa: E402
import live_check_phase1 as lc  # noqa: E402
import stack_lock  # noqa: E402

ROOT = lc.ROOT
OUT_MD = ROOT / "docs" / "results" / "combined_deployment.md"
OUT_JSON = ROOT / "results" / "live-checks" / "combined.json"
checks = cc.checks


def main():
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    approval, chaos = secrets.token_urlsafe(24), secrets.token_urlsafe(24)
    base = {k: v for k, v in os.environ.items() if k not in ("CHAOS_TOKEN", "ETERNALAI_APPROVAL_TOKEN")}
    env = {**base, "ETERNALAI_APPROVAL_TOKEN": approval, "CHAOS_TOKEN": chaos, "EAI_EVALUATOR_TOKEN": approval,
           "OTEL_SDK_DISABLED": "true", "ETERNALAI_MODE": "autopilot", "ETERNALAI_POLICY_FILE": "",
           "GEMINI_API_KEY": "", "GROQ_API_KEY": ""}
    out = {"commit": commit, "execution_id": cc.EXEC_ID, "started": lc.now_ist(), "kind": "combined deployment (not a gate)"}
    stack_lock.take("main", f"combined deployment check at {commit}", f"plan-complete@{commit}")
    api = lc.Api(approval)
    try:
        b = lc.run(["docker", "compose", "--profile", "releases", "build"], env, timeout=3600)
        if not lc.check("B1", "every image builds from this commit", b.returncode == 0, f"exit {b.returncode}"):
            return
        imgs = lc.run(["docker", "compose", "--profile", "releases", "config", "--images"], env).stdout.split()
        out["images"] = {i: lc.run(["docker", "image", "inspect", "--format", "{{.Id}}", i], env).stdout.strip()
                         for i in sorted(set(imgs))}
        services = [s for s in lc.run(["docker", "compose", "config", "--services"], env).stdout.split() if s != "jaeger"]
        if lc.run(["docker", "compose", "up", "-d", "--force-recreate", *services], env, timeout=900).returncode:
            lc.check("B2", "stack starts", False)
            return
        if not lc.check("B2.up", "brain answers /status", cc.wait_brain(api)):
            return
        lc.run([sys.executable, "scripts/stock_gate.py", "--restock", "--force"], env, timeout=300)
        st = cc.verify_restored(api, env)
        lc.check("B2", "the brain runs this commit's data files (SHA256) and margin 0.121529", st["restored"], st)
        s = cc.run_controlled(api, env, "crash", "web")
        lc.check("B3", "smoke: a real crash on web is restarted by autopilot",
                 any(x[0] == "restart_service" and x[2] == "autopilot" for x in s["audited_actions"]),
                 {"audited_actions": s["audited_actions"], "incidents": cc.summary(s["incidents"])})
        # B4: a real latency fault on web, and the dashboard container checked while it is active
        rid = lc.start_run(api, "latency", "web")
        res = {}

        def dash():
            r = subprocess.run([sys.executable, "scripts/live_check_dashboard_charts.py", "--url", "http://127.0.0.1:8050",
                                "--backend", "http://127.0.0.1:8000", "--service", "web", "--populated", "120",
                                "--warmup", "10", "--out", "docs/results/dashboard_charts_combined.md", "--tag", "combined",
                                "--note", f"all images built from `{commit}`; dashboard served by its container (eai-dashboard-1); "
                                          f"real latency fault on web (evaluator run {rid})"],
                               cwd=ROOT, env={**env, "PYTHONIOENCODING": "utf-8", "EAI_EXEC_ID": cc.EXEC_ID},
                               capture_output=True, text=True, timeout=900)
            res.update(exit=r.returncode, tail=r.stdout[-1500:])

        t = threading.Thread(target=dash)
        t.start()
        rev = lc.wait_run(api, rid)
        t.join()
        lc.check("B4", "the dashboard container passes D1-D6 with a populated explanation during a real latency fault",
                 res.get("exit") == 0, {"dashboard_check_exit": res.get("exit"), "run_score": (rev or {}).get("score"),
                                         "report": "docs/results/dashboard_charts_combined.md"})
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
    L = ["# Combined deployment check (generated by `scripts/live_check_combined.py`)", "",
         f"- Commit: `{out['commit']}`; execution ID: `{out['execution_id']}`; started {out['started']}, finished "
         f"{out.get('finished', 'not finished')}.",
         "- The integrated revision as deployed: every image built from this commit, the dashboard served by its container. "
         "**Not release-gate evidence for any candidate.**",
         f"- Result: **{n} of {len(checks)} checks passed**. Raw record: `results/live-checks/combined.json`.", "",
         "| check | what | result | detail |", "|---|---|---|---|"]
    for c in checks:
        d = c["detail"] if isinstance(c["detail"], str) else json.dumps(c["detail"], default=str)
        L.append(f"| `{c['id']}` | {c['what']} | {c['result']} | {d.replace('|', '/')[:900]} |")
    OUT_MD.write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
