"""Overnight sequence from a checkout pinned to one commit (clean attribution).

    python scripts/run_v3_sequence.py            # run from a worktree at the commit to test, detached

1. Wait until the Docker lock is FREE, then TAKE it (scripts/stack_lock.py) and hold it for the whole sequence: the image
   build and every step run under it; child scripts run in parent mode (EAI_STACK_LOCK_PARENT=main) so they never release
   it in between. The lock is released in a `finally`, also after a failure or an exception.
2. Build all images once (attribution: the commit of this checkout).
3. Gate checks: Phase 1 live check, Phase 4a live check; after the evaluation, the controlled checks (G4-G6). Their PASS
   counts are written to results/v3-gate.json. The sequence
   never promotes anything: a demo-stable tag is a separate, manual step that requires every gate item in
   docs/RELEASE_GATE.md, and a failed gate check means no promotion.
4. Evaluation v3 (docs/EVALUATION_V3_PLAN.md). It runs whether or not the gate passes: it is an evaluation, not a gate.
"""
from __future__ import annotations

import json
import os
import re
import secrets
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import stack_lock  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DOCKER_BIN = r"C:\Program Files\Docker\Docker\resources\bin"
LOG = ROOT / "results" / "v3-sequence.log"
GATE = ROOT / "results" / "v3-gate.json"


def log(msg):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(f"{stack_lock.ist()} {msg}\n")


def step(cmd, timeout):
    env = {**os.environ, "PATH": os.environ.get("PATH", "") + os.pathsep + DOCKER_BIN,
           stack_lock.PARENT_ENV: "main",
           "CHAOS_TOKEN": secrets.token_urlsafe(24)}          # only for compose interpolation during the build
    with open(LOG, "a", encoding="utf-8") as f:
        try:
            rc = subprocess.run(cmd, cwd=ROOT, env=env, stdout=f, stderr=subprocess.STDOUT, timeout=timeout).returncode
        except subprocess.TimeoutExpired:
            rc = "timeout"
    log(f"{' '.join(cmd[:4])} -> exit {rc}")
    return rc


def passed(md: Path, commit: str) -> str | None:
    """'x/y' from a results file written by THIS run: the file must name this commit (the checkout also contains older
    committed results files, which must never be read as this run's result)."""
    if not md.exists():
        return None
    text = md.read_text(encoding="utf-8")
    if f"`{commit}`" not in text:
        return None
    m = re.search(r"(\d+) of (\d+) checks passed", text)
    return f"{m.group(1)}/{m.group(2)}" if m else None


def main():
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    log(f"sequence start at commit {commit}")
    while not stack_lock.state().startswith("FREE"):
        time.sleep(60)
    stack_lock.take("main", f"overnight sequence (build, gate checks, evaluation v3) at {commit}", f"plan-complete@{commit}")
    log("lock taken")
    gate = {"commit": commit}
    try:
        py = sys.executable
        if step(["docker", "compose", "--profile", "releases", "build"], 3600):
            log("build failed: stop (no gate checks, no evaluation)")
            gate["build"] = "failed"
            return
        gate["build"] = "ok"
        gate["phase1_exit"] = step([py, "-u", "scripts/live_check_phase1.py"], 3600)
        gate["phase1"] = passed(ROOT / "docs" / "results" / "live_check_phase1.md", commit)
        gate["phase4a_exit"] = step([py, "-u", "scripts/live_check_phase4a.py", "--no-build"], 3600)
        gate["phase4a"] = passed(ROOT / "docs" / "results" / "live_check_phase4a.md", commit)
        GATE.write_text(json.dumps(gate, indent=1), encoding="utf-8")
        log(f"gate so far: {gate}")
        gate["eval_exit"] = step([py, "-u", "scripts/run_final_eval.py"], 10 * 3600)
        # controlled checks (docs/RELEASE_GATE.md G4-G6): after the registered evaluation, same commit and build
        gate["controlled_exit"] = step([py, "-u", "scripts/live_check_controlled.py"], 3 * 3600)
        gate["controlled"] = passed(ROOT / "docs" / "results" / "live_check_controlled.md", commit)
        gate["live_gate_items_all_passed"] = all(
            v is not None and v.split("/")[0] == v.split("/")[1] for v in (gate["phase1"], gate["phase4a"], gate["controlled"]))
        log(f"gate: {gate}")
        log("sequence finished")
    finally:
        GATE.write_text(json.dumps(gate, indent=1), encoding="utf-8")
        stack_lock.release("main", f"plan-complete@{commit}")
        log("lock released")


if __name__ == "__main__":
    main()
