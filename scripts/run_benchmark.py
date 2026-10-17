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


def stop_brain():
    sh("docker compose stop eternalai")


def approver(stop, token, after):
    """Simulated operator: approve any pending proposal once it has waited `after` seconds."""
    first_seen = {}
    while not stop.is_set():
        try:
            for a in httpx.get(f"{EAI}/approvals", timeout=3).json():
                t0 = first_seen.setdefault(a["incident_id"], time.time())
                if time.time() - t0 >= after:
                    httpx.post(f"{EAI}/approvals/{a['incident_id']}/approve", json={"approver": "benchmark-operator"},
                               headers={"X-Approval-Token": token}, timeout=5)
        except (httpx.HTTPError, ValueError):
            pass
        time.sleep(1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", required=True, choices=list(ARMS))
    ap.add_argument("--reps", type=int, default=5)
    ap.add_argument("--seed0", type=int, default=100)
    ap.add_argument("--approve-after", type=float, default=5.0)
    ap.add_argument("--scenarios", nargs="*", default=SCENARIOS)
    ap.add_argument("--manage-stack", action="store_true", help="(re)start / stop the brain container for this arm")
    ap.add_argument("--smoke", action="store_true", help="plumbing check on seeds that are in neither the training (1000-1707) "
                    "nor the benchmark (<1000) range; results go to docs/results/benchmark_smoke.jsonl and are not reported")
    a = ap.parse_args()
    global RAW
    if a.smoke:
        a.seed0, RAW = max(a.seed0, 2000), Path("docs/results/benchmark_smoke.jsonl")
    else:
        assert a.seed0 + a.reps * 10 + 9 < 1000, "benchmark seeds must stay below the training seeds (1000+)"
    brain, mode = ARMS[a.arm]
    token = os.getenv("ETERNALAI_APPROVAL_TOKEN", "benchmark-token-not-a-secret")
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
    stop = threading.Event()
    if a.arm == "eternalai_ask_first":
        threading.Thread(target=approver, args=(stop, token, a.approve_after), daemon=True).start()
    try:
        for rep in range(a.reps):
            for si, scen in scenario_order(100 + rep, a.scenarios):
                seed = a.seed0 + rep * 10 + SCENARIOS.index(scen)
                if (a.arm, scen, seed) in done:
                    continue
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
                                                            "abstained", "ranking", "actions", "verification", "timeline")}
                                     for i in httpx.get(f"{EAI}/incidents", timeout=10).json()
                                     if i["opened_t"] >= truth["t_inject"] - 1]
                    except (httpx.HTTPError, ValueError):
                        pass
                row = {"arm": a.arm, "scenario": scen, "seed": seed, "rep": rep, "score": score, "params": truth["params"],
                       "target": truth["target"], "incidents": incidents, "brain_status": {
                           k: meta.get(k) for k in ("brain", "mode", "model_meta", "calibration", "fallbacks_in_use")},
                       "approve_after_s": a.approve_after if a.arm == "eternalai_ask_first" else None,
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
