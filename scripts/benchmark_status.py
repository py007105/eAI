"""Read-only benchmark progress: completed runs out of 225, per-cell counts, heartbeat. Prints COUNTS ONLY, never result values.

    python scripts/benchmark_status.py [--raw PATH_TO_benchmark_raw.jsonl] [--log PATH_TO_benchmark_progress.log]

Uses file modification times (no locks taken), one tiny HTTP request each to the brain and the evaluator, and one process listing.
"""
import argparse
import json
import os
import subprocess
import time
from pathlib import Path

import httpx

ARMS = ["eternalai_autopilot", "eternalai_ask_first", "threshold_restart", "prototype_rules", "no_action"]  # run order
SCENARIOS = ["crash", "latency", "error_spike", "memory_leak", "disk_fill", "bad_deploy", "cpu_burn", "traffic_surge", "good_deploy"]
REPS = 5


def age(path: Path) -> str:
    try:
        s = time.time() - os.stat(path).st_mtime
        return f"{s:.0f} s ago" if s < 120 else f"{s / 60:.1f} min ago"
    except OSError:
        return "missing"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default="docs/results/benchmark_raw.jsonl")
    ap.add_argument("--log", default="runtime/benchmark_progress.log")
    a = ap.parse_args()
    raw, log = Path(a.raw), Path(a.log)
    cells: dict[tuple[str, str], set[int]] = {}
    total = 0
    if raw.exists():
        for line in raw.read_text().splitlines():
            try:
                r = json.loads(line)
            except ValueError:
                continue
            cells.setdefault((r["arm"], r["scenario"]), set()).add(r["seed"])   # a seed counts once
    total = sum(len(v) for v in cells.values())
    planned = len(ARMS) * len(SCENARIOS) * REPS
    print(f"completed runs: {total} / {planned}")
    print(f"{'arm':22s} " + " ".join(f"{s[:7]:>7s}" for s in SCENARIOS) + "   total")
    for arm in ARMS:
        counts = [len(cells.get((arm, s), ())) for s in SCENARIOS]
        print(f"{arm:22s} " + " ".join(f"{c:>7d}" for c in counts) + f"   {sum(counts)}/{len(SCENARIOS) * REPS}")
    print(f"\nheartbeat: raw results last written {age(raw)}; progress log last written {age(log)}")
    try:   # last progress line, if the log is not momentarily locked by its writer
        lines = log.read_text(errors="replace").splitlines()
        print("last progress line (arm start/end markers only): " +
              next((x for x in reversed(lines) if " arm " in x), "none yet"))
    except OSError:
        print("progress log is locked by its writer right now (normal)")
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command",
                              "Get-CimInstance Win32_Process | ? { $_.CommandLine -match 'run_all_arms|run_benchmark' } | "
                              "% { $_.CommandLine }"], capture_output=True, text=True, timeout=30).stdout
        arms_running = sorted({x.split("--arm")[1].split()[0] for x in out.splitlines() if "--arm" in x})
        print(f"driver running: {'run_all_arms' in out}; runner currently on arm: {arms_running or 'none'}")
    except (OSError, subprocess.SubprocessError):
        print("could not list processes")
    for name, url, key in (("evaluator", "http://localhost:8200/health", "ok"), ("brain", "http://localhost:8000/status", "brain")):
        try:
            j = httpx.get(url, timeout=3).json()
            print(f"{name}: up" + (f" (brain={j.get('brain')}, mode={j.get('mode')})" if name == "brain" else ""))
        except (httpx.HTTPError, ValueError):
            print(f"{name}: not answering (expected for the brain during the no_action arm or between arms)")


if __name__ == "__main__":
    main()
