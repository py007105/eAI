"""Overnight sequence from a checkout pinned to one commit (clean attribution).

    python tools/run_v3_sequence.py            # run from a worktree at the commit to test, detached

1. Ownership: wait until the Docker lock is free, then TAKE it atomically (tools/stack_lock.py: owner file created with
   O_EXCL; seeing FREE is not ownership). Hold it for the whole sequence: the image build and every step run under it;
   children run in parent mode with the owner token, so they never release it in between. Released in a `finally`,
   and only with this sequence's own token.
2. Execution identity: a unique execution ID; every step gets it (EAI_EXEC_ID) and writes it into its results; all
   outputs are copied with their SHA256 into a FRESH folder results/executions/<ID>/; the manifest there records the
   commit, the image IDs after the build, the configuration (rulebook and artifact hashes), and per step the command,
   start and end time, exit status and output files.
3. Fail closed: a gate step counts as passed only if its results file was written during that step, names this commit
   and this execution ID, and reports every check passed. Missing, partial, stale or mismatched results are failures. A
   process exiting with 0 is not a pass. The sequence never promotes anything.
4. Steps: build; Phase 1 live check; Phase 4a live check; evaluation v3 (docs/EVALUATION_V3_PLAN.md; complete only with
   all 50 rows); controlled checks and the unmodified smoke check (docs/RELEASE_GATE.md G4-G7).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import stack_lock  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DOCKER_BIN = r"C:\Program Files\Docker\Docker\resources\bin"
EXEC_ID = f"{time.strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:8]}"
EXEC_DIR = ROOT / "results" / "executions" / EXEC_ID
LOG = EXEC_DIR / "sequence.log"
MANIFEST = EXEC_DIR / "manifest.json"
CONFIG_FILES = ["engine/rulebooks/default.yaml", "ml/models/artifacts/root_margin.json", "ml/models/artifacts/detectors.joblib",
                "ml/models/artifacts/classifier.joblib", "ml/models/artifacts/ranker.joblib", "ml/data/kb/MANIFEST.json",
                "ml/data/kb/outcomes_measured.csv", "docker-compose.yml"]
STEPS = [  # name, command, results file (relative to ROOT) or None, timeout s
    ("phase1", ["tools/live_check_phase1.py"], "docs/results/live_check_phase1.md", 3600),
    ("phase4a", ["tools/live_check_phase4a.py", "--no-build"], "docs/results/live_check_phase4a.md", 3600),
    ("eval_v3", ["tools/run_final_eval.py"], None, 10 * 3600),
    ("controlled", ["tools/live_check_controlled.py"], "docs/results/live_check_controlled.md", 3 * 3600),
]
EXTRA_OUTPUTS = {"phase1": ["results/live-checks/phase1.json"], "phase4a": ["results/live-checks/phase4a.json"],
                 "controlled": ["results/live-checks/controlled.json"],
                 "eval_v3": [f"results/benchmark-v3/{EXEC_ID}/raw.jsonl", "docs/results/benchmark_v3.md"]}


def sha256(p: Path) -> str | None:
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None


def log(msg):
    EXEC_DIR.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(f"{stack_lock.ist()} {msg}\n")


def save(manifest):
    MANIFEST.write_text(json.dumps(manifest, indent=1), encoding="utf-8")


def run_step(cmd, timeout, token, manifest, name):
    env = {**os.environ, "PATH": os.environ.get("PATH", "") + os.pathsep + DOCKER_BIN,
           stack_lock.PARENT_ENV: "main", stack_lock.TOKEN_ENV: token, "EAI_EXEC_ID": EXEC_ID,
           "CHAOS_TOKEN": secrets.token_urlsafe(24)}          # only for compose interpolation during the build
    rec = {"name": name, "command": " ".join(cmd), "start": stack_lock.ist(), "start_epoch": time.time()}
    manifest["steps"].append(rec)
    save(manifest)
    with open(EXEC_DIR / f"{name}.out.log", "a", encoding="utf-8") as f:
        try:
            rec["exit"] = subprocess.run(cmd, cwd=ROOT, env=env, stdout=f, stderr=subprocess.STDOUT, timeout=timeout).returncode
        except subprocess.TimeoutExpired:
            rec["exit"] = "timeout"
    rec["end"], rec["end_epoch"] = stack_lock.ist(), time.time()
    save(manifest)
    log(f"{name}: exit {rec['exit']}")
    return rec


def collect(rec, files):
    """Copy outputs written during this step into the execution folder; a file not modified during the step is stale."""
    rec["outputs"] = []
    for rel in files:
        src = ROOT / rel
        fresh = src.exists() and src.stat().st_mtime >= rec["start_epoch"] - 1
        entry = {"path": rel, "exists": src.exists(), "written_during_step": fresh, "sha256": sha256(src) if fresh else None}
        if fresh:
            dst = EXEC_DIR / "outputs" / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
        rec["outputs"].append(entry)


def verdict(rec, results_rel, commit) -> dict:
    """Fail closed: only a results file written during this step, naming this commit and this execution, with every check
    passed, is a pass."""
    out = next((o for o in rec.get("outputs", []) if o["path"] == results_rel), None)
    if not out or not out["written_during_step"]:
        return {"status": "FAIL", "reason": "results file missing or not written by this step (stale)"}
    text = (ROOT / results_rel).read_text(encoding="utf-8")
    if f"`{commit}`" not in text or f"`{EXEC_ID}`" not in text:
        return {"status": "FAIL", "reason": "results file does not name this commit and execution"}
    m = re.search(r"(\d+) of (\d+) checks passed", text)
    if not m:
        return {"status": "FAIL", "reason": "no pass count in the results file (partial run?)"}
    n, total = int(m.group(1)), int(m.group(2))
    inc = re.search(r"INCOMPLETE: (\d+)", text)
    return {"status": "PASS" if n == total and total > 0 else "FAIL", "passed": f"{n}/{total}",
            "incomplete": int(inc.group(1)) if inc else 0}


def image_ids() -> dict:
    env = {**os.environ, "PATH": os.environ.get("PATH", "") + os.pathsep + DOCKER_BIN, "CHAOS_TOKEN": "x"}
    imgs = subprocess.run(["docker", "compose", "--profile", "releases", "config", "--images"], cwd=ROOT, env=env,
                          capture_output=True, text=True).stdout.split()
    out = {}
    for i in sorted(set(imgs)):
        r = subprocess.run(["docker", "image", "inspect", "--format", "{{.Id}}", i], env=env, capture_output=True, text=True)
        out[i] = r.stdout.strip() or None
    return out


def main():
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"], cwd=ROOT, capture_output=True,
                           text=True).stdout.strip()
    EXEC_DIR.mkdir(parents=True, exist_ok=False)          # a fresh folder: never reused
    manifest = {"execution_id": EXEC_ID, "commit": commit, "checkout": str(ROOT), "tracked_changes_at_start": dirty or None,
                "configuration": {rel: sha256(ROOT / rel) for rel in CONFIG_FILES},
                "runtime_config": {"rulebook": "default.yaml", "mode": "per step (autopilot unless the step says otherwise)",
                                   "telemetry": "T3 (no Jaeger)", "llm_keys": "empty in the evaluation; unset in live checks"},
                "steps": [], "completion": "running"}
    save(manifest)
    log(f"sequence start at commit {commit}, execution {EXEC_ID}")
    if dirty:
        manifest["completion"] = "refused: the checkout has tracked changes"
        save(manifest)
        return
    token = None
    while token is None:
        if stack_lock.is_free():
            try:
                token = stack_lock.take("main", f"overnight sequence {EXEC_ID} at {commit}", f"plan-complete@{commit}")
            except SystemExit as e:          # another session won the race: keep waiting
                log(f"lock not acquired: {e}")
        if token is None:
            time.sleep(60)
    manifest["lock_taken"] = stack_lock.ist()
    save(manifest)
    log("lock taken (owner file created atomically)")
    try:
        py = sys.executable
        b = run_step(["docker", "compose", "--profile", "releases", "build"], 3600, token, manifest, "build")
        manifest["images"] = image_ids()
        save(manifest)
        if b["exit"] != 0:
            manifest["completion"] = "incomplete: build failed"
            return
        for name, cmd, results_rel, timeout in STEPS:
            rec = run_step([py, "-u", *cmd], timeout, token, manifest, name)
            collect(rec, ([results_rel] if results_rel else []) + EXTRA_OUTPUTS.get(name, []))
            if name == "eval_v3":
                raw = ROOT / f"results/benchmark-v3/{EXEC_ID}/raw.jsonl"
                rows = len(raw.read_text(encoding="utf-8").splitlines()) if raw.exists() else 0
                rec["verdict"] = {"status": "COMPLETE" if rows == 50 else "INCOMPLETE", "rows": rows, "expected_rows": 50}
            else:
                rec["verdict"] = verdict(rec, results_rel, commit)
            save(manifest)
        gate = {r["name"]: r["verdict"]["status"] for r in manifest["steps"] if r["name"] in ("phase1", "phase4a", "controlled")}
        manifest["gate_live_items_all_passed"] = len(gate) == 3 and all(v == "PASS" for v in gate.values())
        manifest["completion"] = "complete"
    except Exception as e:  # noqa: BLE001
        manifest["completion"] = f"incomplete: {type(e).__name__}: {e}"
        raise
    finally:
        manifest["finished"] = stack_lock.ist()
        save(manifest)
        stack_lock.release("main", f"plan-complete@{commit}", token=token)
        log("lock released")


if __name__ == "__main__":
    main()
