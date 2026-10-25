"""Phase 3 live check: the forecast check (docs/FORECAST_CHECK.md, v3) on the real Compose stack, brain in WATCH-ONLY mode.

    python tools/live_check_phase3.py --smoke     # 2 runs on excluded seeds 3900 (memory_leak) and 3901 (disk_fill, gradual)
    python tools/live_check_phase3.py             # the 20 pre-registered runs, seeds 3000-3004

Takes the shared Docker lock (D:\\eAI\\STACK_LOCK.md, see docs/HANDOFF_FRIEND.md section 1.5), rebuilds the images from this
checkout, starts the stack (telemetry condition T3, as tools/demo.ps1) with a throwaway approval token and chaos token passed
through the environment only (never printed or written), runs `tools/forecast_check.py collect`, then `analyze`, stops the
stack and releases the lock.
"""
from __future__ import annotations

import argparse
import os
import secrets
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
import stack_lock  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DOCKER_BIN = r"C:\Program Files\Docker\Docker\resources\bin"
IST = timezone(timedelta(hours=5, minutes=30))


def ist() -> str:
    return datetime.now(IST).strftime("%Y-%m-%d %H:%M IST")


def run(cmd, env, timeout=1800, check=False):
    e = {**env, "PATH": env.get("PATH", "") + os.pathsep + DOCKER_BIN}
    r = subprocess.run(cmd, cwd=ROOT, env=e, capture_output=True, text=True, timeout=timeout)
    if check and r.returncode:
        raise SystemExit(f"{' '.join(cmd[:4])} failed: {r.stderr[-400:]}")
    return r


def take_lock(what: str, commit: str):
    stack_lock.take("main", what, f"plan-complete@{commit}")


def release_lock(commit: str):
    stack_lock.release("main", f"plan-complete@{commit}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--no-build", action="store_true")
    a = ap.parse_args()
    commit = run(["git", "rev-parse", "--short", "HEAD"], dict(os.environ)).stdout.strip()
    approval, chaos = secrets.token_urlsafe(24), secrets.token_urlsafe(24)
    base = {k: v for k, v in os.environ.items() if k not in ("CHAOS_TOKEN", "ETERNALAI_APPROVAL_TOKEN")}
    env = {**base, "ETERNALAI_APPROVAL_TOKEN": approval, "CHAOS_TOKEN": chaos, "EAI_EVALUATOR_TOKEN": approval,
           "OTEL_SDK_DISABLED": "true", "ETERNALAI_MODE": "watch-only", "ETERNALAI_POLICY_FILE": ""}
    take_lock("forecast check (Phase 3)" + (" smoke" if a.smoke else ""), commit)
    try:
        if not a.no_build:
            print(f"{ist()} building images", flush=True)
            run(["docker", "compose", "--profile", "releases", "build"], env, check=True)
        services = [s for s in run(["docker", "compose", "config", "--services"], env).stdout.split() if s != "jaeger"]
        run(["docker", "compose", "up", "-d", "--force-recreate", *services], env, check=True)
        for _ in range(80):
            try:
                if httpx.get("http://localhost:8000/status", timeout=3).json().get("mode") == "watch-only":
                    break
            except (httpx.HTTPError, ValueError):
                pass
            time.sleep(3)
        else:
            raise SystemExit("brain did not come up in watch-only mode")
        time.sleep(45)
        r = run([sys.executable, "tools/stock_gate.py", "--restock", "--force"], env, timeout=300)
        print(f"{ist()} stock gate exit {r.returncode}", flush=True)
        if a.smoke:
            raw, out = "results/forecast-check/v3-smoke", "results/forecast-check/v3-smoke.md"
            for sc, seed in (("memory_leak", 3900), ("disk_fill", 3901)):
                r = run([sys.executable, "tools/forecast_check.py", "collect", "--out", raw, "--seeds", str(seed), "--only", sc],
                        env, timeout=1200)
                print(r.stdout.strip()[-300:], r.stderr.strip()[-300:], flush=True)
        else:
            raw, out = "results/forecast-check/v3-raw", "docs/results/forecast_check.md"
            r = run([sys.executable, "tools/forecast_check.py", "collect", "--out", raw], env, timeout=4 * 3600)
            print(r.stdout.strip()[-1500:], r.stderr.strip()[-500:], flush=True)
        r = run([sys.executable, "tools/forecast_check.py", "analyze", "--raw", raw, "--out", out], env, timeout=300)
        print(r.stdout[-6000:], r.stderr[-500:], flush=True)
    finally:
        run(["docker", "compose", "stop"], env, timeout=300)
        release_lock(commit)
        print(f"{ist()} stack stopped, lock released", flush=True)


if __name__ == "__main__":
    main()
