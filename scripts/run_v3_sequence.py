"""Overnight sequence from a checkout pinned to one commit (clean attribution): wait for the Docker lock to be free, build all
images once, run the demo gate checks (Phase 1 and Phase 4a live checks) and then evaluation v3.

    python scripts/run_v3_sequence.py            # run from a worktree at the commit to test, detached

Each step writes its own results inside this checkout; the main session copies them back and commits them.
"""
from __future__ import annotations

import os
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


def log(msg):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(f"{stack_lock.ist()} {msg}\n")


def step(cmd, timeout):
    env = {**os.environ, "PATH": os.environ.get("PATH", "") + os.pathsep + DOCKER_BIN,
           "CHAOS_TOKEN": secrets.token_urlsafe(24)}          # only for compose interpolation during the build
    with open(LOG, "a", encoding="utf-8") as f:
        rc = subprocess.run(cmd, cwd=ROOT, env=env, stdout=f, stderr=subprocess.STDOUT, timeout=timeout).returncode
    log(f"{' '.join(cmd[:4])} -> exit {rc}")
    return rc


def main():
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    log(f"sequence start at commit {commit}")
    while not stack_lock.state().startswith("FREE"):
        time.sleep(60)
    log("lock free")
    py = sys.executable
    if step(["docker", "compose", "--profile", "releases", "build"], 3600):
        log("build failed: stop")
        return
    step([py, "-u", "scripts/live_check_phase1.py"], 3600)
    step([py, "-u", "scripts/live_check_phase4a.py", "--no-build"], 3600)
    step([py, "-u", "scripts/run_final_eval.py"], 10 * 3600)
    log("sequence finished")


if __name__ == "__main__":
    main()
