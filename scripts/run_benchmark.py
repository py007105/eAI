"""Held-out benchmark runner. One arm per invocation; results are appended to docs/results/benchmark_raw.jsonl.

    python scripts/run_benchmark.py --arm eternalai_autopilot --reps 5 [--seed0 100] [--manage-stack]

Arms (all use the SAME seeds, so scenario, target and fault parameters are identical across arms: a paired design):
  no_action             EternalAI is not running; the evaluator injects, waits, restores.
  threshold_restart     ETERNALAI_BRAIN=threshold_restart, autopilot
  prototype_rules       ETERNALAI_BRAIN=prototype_rules, autopilot
  eternalai_ask_first   the real brain; a simulated operator approves each proposal after --approve-after seconds
  eternalai_autopilot   the real brain, autopilot

Seeds are < 1000, disjoint from the training seeds (>= 1000). The models are frozen and must not be retuned after seeing
these results; if something has to change it is a NEW model version and the benchmark is rerun on fresh seeds (--seed0).
The runner records the model metadata (git commit, data hash) of the brain under test with every row. No LLM key is
passed to the brain here, so every report is the template report (the live-LLM comparison is a separate step).
"""
import argparse
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "models"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import memguard  # noqa: E402
from collect_runs import SCENARIOS, scenario_order  # noqa: E402

EV = os.getenv("EVALUATOR_URL", "http://localhost:8200")
EAI = os.getenv("EAI_PUBLIC_URL", "http://localhost:8000")
RAW = Path("docs/results/benchmark_raw.jsonl")
TIMEOUT = {"memory_leak": 120, "disk_fill": 100}
DEFAULT_TIMEOUT = 90
ARMS = {"no_action": (None, None), "threshold_restart": ("threshold_restart", "autopilot"),
        "prototype_rules": ("prototype_rules", "autopilot"), "eternalai_ask_first": ("eternalai", "ask-first"),
        "eternalai_autopilot": ("eternalai", "autopilot")}
DOCKER = r"C:\Program Files\Docker\Docker\resources\bin"
SYSTEM_COMMIT = subprocess.run("git rev-parse --short HEAD", shell=True, capture_output=True, text=True).stdout.strip()


def sh(cmd, **env):
    e = {**os.environ, **{k: str(v) for k, v in env.items()}}
    e["PATH"] = e.get("PATH", "") + os.pathsep + DOCKER
    return subprocess.run(cmd, shell=True, env=e, capture_output=True, text=True)


def start_brain(brain, mode, token):
    r = sh("docker compose up -d --force-recreate --no-deps eternalai", ETERNALAI_BRAIN=brain, ETERNALAI_MODE=mode,
           ETERNALAI_APPROVAL_TOKEN=token, GEMINI_API_KEY="", GROQ_API_KEY="")
    if r.returncode:
        sys.exit(f"could not start the brain: {r.stderr[-300:]}")
    for _ in range(90):
        try:
            st = httpx.get(f"{EAI}/status", timeout=3).json()
            if st.get("brain") == brain and st.get("mode") == mode:
                time.sleep(15)   # let the rolling windows fill with healthy data
                return st
        except (httpx.HTTPError, ValueError):
            pass
        time.sleep(2)
    sys.exit("the brain did not come up in the expected brain/mode")


def benchmark_token():
    """The approval token for the brain under test and for the simulated operator.

    v1 read ETERNALAI_APPROVAL_TOKEN here. But this module imports models/collect_runs.py, which imports eternalai/config.py, which calls
    load_dotenv(); that put the .env value ("change-me", copied from .env.example) into the environment before main() ran. The harness then started the
    brain with "change-me", which the brain treats as "approval API disabled" (HTTP 503), and the operator sent the same value and ignored the 503. So no
    ask-first proposal could ever be approved (docs/postmortems/ask-first-arm-stuck-incident-v1.md). The token now comes from its own variable and is
    never taken from ETERNALAI_APPROVAL_TOKEN.
    """
    return os.environ.get("EAI_BENCH_TOKEN") or "benchmark-token-not-a-secret"


def verify_approval_api(token):
    """Abort unless the running brain accepts this token. A probe approve for an incident that does not exist must be answered 409 (no pending
    approval); 503 means the approval API is disabled (placeholder token) and 403 means a different token."""
    r = httpx.post(f"{EAI}/approvals/__probe__/approve", json={"approver": "benchmark-preflight"}, headers={"X-Approval-Token": token}, timeout=10)
    if r.status_code != 409:
        sys.exit(f"the brain does not accept the benchmark approval token (probe answered HTTP {r.status_code}: {r.text[:120]}); ask-first cannot work")
    return True


def stop_brain():
    sh("docker compose stop eternalai")


def reset_brain(token, tries=12):
    """v2 (item D): clear the brain's per-run state before every run. Retries while an action is still in flight; returns what happened, which is
    recorded in the row. A failure is recorded, not hidden (the run still goes ahead)."""
    last = None
    for _ in range(tries):
        try:
            r = httpx.post(f"{EAI}/admin/reset", headers={"X-Approval-Token": token}, timeout=10)
            last = {"status": r.status_code, **(r.json() if r.headers.get("content-type", "").startswith("application/json") else {})}
            if r.status_code in (200, 404):   # 404: the brain under test has no reset endpoint (a v1 image); nothing to retry
                return last
        except (httpx.HTTPError, ValueError) as e:
            last = {"error": f"{type(e).__name__}: {e}"}
        time.sleep(5)
    print(f"RESET failed after {tries} tries: {last}", flush=True)
    return last


def approver(stop, token, after, stats=None):
    """Simulated operator: approve any pending proposal once it has waited `after` seconds.

    v2 (item C): every GET and approve call is checked and logged. v1 swallowed every error and ignored the status of the approve call, so
    the progress log could not say why an ask-first proposal was never approved. `stats` (a dict) collects counts that go into the result row.
    """
    stats = stats if stats is not None else {}
    stats.update({"approved": 0, "approve_failures": 0, "poll_errors": 0, "thread_errors": 0, "last_status": None})
    first_seen, approved = {}, set()
    while not stop.is_set():
        try:
            r = httpx.get(f"{EAI}/approvals", timeout=3)
            if r.status_code != 200:
                stats["poll_errors"] += 1
                print(f"APPROVER poll: HTTP {r.status_code} {r.text[:120]}", flush=True)
            else:
                for a in r.json():
                    iid = a["incident_id"]
                    t0 = first_seen.setdefault(iid, time.time())
                    if iid in approved or time.time() - t0 < after:
                        continue
                    p = httpx.post(f"{EAI}/approvals/{iid}/approve", json={"approver": "benchmark-operator"},
                                   headers={"X-Approval-Token": token}, timeout=5)
                    stats["last_status"] = p.status_code
                    if p.status_code == 200:
                        approved.add(iid)
                        stats["approved"] += 1
                        print(f"APPROVER approved {iid} ({a['runbook_id']} on {a['service']}) after {time.time() - t0:.1f}s", flush=True)
                    else:
                        stats["approve_failures"] += 1
                        print(f"APPROVER approve {iid}: HTTP {p.status_code} {p.text[:120]}", flush=True)
        except (httpx.HTTPError, ValueError) as e:
            stats["poll_errors"] += 1
            print(f"APPROVER transient {type(e).__name__}: {e}", flush=True)
        except Exception as e:  # noqa: BLE001 - v1 let anything else kill this thread silently; log it and keep going
            stats["thread_errors"] += 1
            print(f"APPROVER unexpected {type(e).__name__}: {e}", flush=True)
        time.sleep(1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", required=True, choices=list(ARMS))
    ap.add_argument("--reps", type=int, default=5)
    ap.add_argument("--seed0", type=int, default=100)
    ap.add_argument("--approve-after", type=float, default=5.0)
    ap.add_argument("--scenarios", nargs="*", default=SCENARIOS)
    ap.add_argument("--manage-stack", action="store_true", help="(re)start / stop the brain container for this arm")
    ap.add_argument("--models-label", default="models-v1 (frozen; see docs/MODEL_CARD.md)", help="recorded with every row")
    ap.add_argument("--min-free-gb", type=float, default=1.0, help="v2: wait (and log) instead of starting a run while free RAM is below this; 0 disables")
    ap.add_argument("--raw", help="v2: results file (default docs/results/benchmark_raw.jsonl, the v1 file; v2 runs must use their own file)")
    ap.add_argument("--no-reset", action="store_true", help="v1 behaviour: do not reset the brain's per-run state between runs")
    ap.add_argument("--smoke", action="store_true", help="plumbing check on seeds that are in neither the training (1000-1707) "
                    "nor the benchmark (<1000) range; results go to docs/results/benchmark_smoke.jsonl and are not reported")
    a = ap.parse_args()
    global RAW
    if a.raw:
        RAW = Path(a.raw)
    if a.smoke:
        a.seed0, RAW = max(a.seed0, 2000), Path("docs/results/benchmark_smoke.jsonl")
    else:
        assert a.seed0 + a.reps * 10 + 9 < 1000, "benchmark seeds must stay below the training seeds (1000+)"
    brain, mode = ARMS[a.arm]
    token = benchmark_token()
    meta = {}
    if a.manage_stack:
        if brain is None:
            stop_brain()
        else:
            meta = start_brain(brain, mode, token)
    if brain is None:
        try:
            httpx.get(f"{EAI}/status", timeout=2)
            sys.exit("no_action arm: a brain is still answering on the EternalAI port; stop it first")
        except httpx.HTTPError:
            pass
    else:
        meta = httpx.get(f"{EAI}/status", timeout=5).json()
    RAW.parent.mkdir(parents=True, exist_ok=True)
    done = set()
    if RAW.exists():
        for line in RAW.read_text().splitlines():
            r = json.loads(line)
            done.add((r["arm"], r["scenario"], r["seed"]))
    if a.arm == "eternalai_ask_first":
        verify_approval_api(token)
    stop = threading.Event()
    astats = {}
    if a.arm == "eternalai_ask_first":
        threading.Thread(target=approver, args=(stop, token, a.approve_after, astats), daemon=True).start()
    try:
        for rep in range(a.reps):
            for si, scen in scenario_order(100 + rep, a.scenarios):
                seed = a.seed0 + rep * 10 + SCENARIOS.index(scen)
                if (a.arm, scen, seed) in done:
                    continue
                memguard.wait_for_memory(a.min_free_gb)
                reset_res = reset_brain(token) if brain is not None and not a.no_reset else None
                r = httpx.post(f"{EV}/runs", json={"scenario": scen, "seed": seed, "timeout_s": TIMEOUT.get(scen, DEFAULT_TIMEOUT),
                                                   "healthy_s": 60}, timeout=20)
                if r.status_code != 200:
                    print(f"{a.arm} {scen} seed {seed}: could not start ({r.status_code}); skipping")
                    continue
                rid = r.json()["run_id"]
                while httpx.get(f"{EV}/runs/{rid}/status", timeout=10).json()["state"] == "running":
                    time.sleep(3)
                rev = httpx.get(f"{EV}/runs/{rid}/reveal", timeout=10)
                if rev.status_code != 200:
                    err = httpx.get(f"{EV}/runs/{rid}/status", timeout=10).json().get("error", "unknown")
                    print(f"{a.arm} {scen} seed {seed}: run failed ({err}); rerun the arm to retry")
                    continue
                score, truth = rev.json()["score"], rev.json()["truth"]
                incidents = []
                if brain is not None:
                    try:
                        incidents = [{k: i.get(k) for k in ("id", "opened_t", "closed_t", "kind", "status", "likely_cause",
                                                            "abstained", "ranking", "actions", "verification", "timeline",
                                                            "diagnosis", "report_meta", "forecasts", "confidence", "services")}
                                     for i in httpx.get(f"{EAI}/incidents", timeout=10).json()
                                     if i["opened_t"] >= truth["t_inject"] - 1]
                    except (httpx.HTTPError, ValueError):
                        pass
                row = {"arm": a.arm, "scenario": scen, "seed": seed, "rep": rep, "score": score, "params": truth["params"],
                       "target": truth["target"], "incidents": incidents, "brain_status": {
                           k: meta.get(k) for k in ("brain", "mode", "model_meta", "calibration", "fallbacks_in_use")},
                       "approve_after_s": a.approve_after if a.arm == "eternalai_ask_first" else None,
                       "system_commit": SYSTEM_COMMIT, "models": a.models_label,
                       "approver": dict(astats) if a.arm == "eternalai_ask_first" else None, "brain_reset": reset_res,
                       "finished_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
                with RAW.open("a") as f:
                    f.write(json.dumps(row) + "\n")
                print(f"{a.arm} {scen} seed {seed}: detected={score.get('detected')} recovered={score.get('recovered')} "
                      f"failed%={score.get('failed_request_pct')}", flush=True)
    finally:
        stop.set()
        if a.manage_stack and brain is not None:
            stop_brain()


if __name__ == "__main__":
    main()
