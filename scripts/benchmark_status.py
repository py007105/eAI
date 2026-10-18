"""Read-only benchmark progress: completed runs out of 225, per-cell counts, heartbeat. Prints COUNTS ONLY, never result values.

    python scripts/benchmark_status.py [--plan v1|v2] [--raw PATH_TO_benchmark_raw.jsonl] [--log PATH_TO_benchmark_progress.log]

Uses file modification times (no locks taken), one tiny HTTP request each to the brain and the evaluator, and one process listing.
"""
import argparse
import json
import os
import re
import subprocess
import time
from pathlib import Path

import httpx

ARMS = ["eternalai_autopilot", "eternalai_ask_first", "threshold_restart", "prototype_rules", "no_action"]  # run order
SCENARIOS = ["crash", "latency", "error_spike", "memory_leak", "disk_fill", "bad_deploy", "cpu_burn", "traffic_surge", "good_deploy"]
REPS = 5
HEALTHY, SUPPORTED = ["traffic_surge", "good_deploy"], ["crash", "latency", "error_spike", "memory_leak", "disk_fill", "bad_deploy"]
# v2 reduced plan (Amendment 4 section M): planned runs per (arm, scenario)
V2_PLAN = {**{("eternalai_autopilot", s): 12 for s in HEALTHY}, **{("threshold_restart", s): 12 for s in HEALTHY},
           **{("eternalai_ask_first", s): 4 for s in HEALTHY}, **{("eternalai_ask_first", s): 3 for s in SUPPORTED},
           **{("eternalai_autopilot", s): 3 for s in SUPPORTED + ["cpu_burn"]}}
MODEL_HASHES = {"de7253cbdf0f": "models-v1", "2f14ce107a0c": "models-v2"}   # first 12 hex chars of the training-data hash the brain reports
# a process is the driver only if it is a python/powershell process running one of these scripts; the listing command itself and Stage 0/1 tools never match
DRIVER = r"(stage3_eval|run_benchmark|run_all_arms)\.(py|ps1)"


def age(path: Path) -> str:
    try:
        s = time.time() - os.stat(path).st_mtime
        return f"{s:.0f} s ago" if s < 120 else f"{s / 60:.1f} min ago"
    except OSError:
        return "missing"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", choices=["v1", "v2"], default="v1")
    ap.add_argument("--raw", default=None)
    ap.add_argument("--log", default=None)
    a = ap.parse_args()
    a.raw = a.raw or ("results/benchmark-v2/benchmark_v2_raw.jsonl" if a.plan == "v2" else "docs/results/benchmark_raw.jsonl")
    a.log = a.log or ("results/benchmark-v2/stage3_driver.log" if a.plan == "v2" else "runtime/benchmark_progress.log")
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
    plan = V2_PLAN if a.plan == "v2" else {(arm, s): REPS for arm in ARMS for s in SCENARIOS}
    planned = sum(plan.values())
    print(f"plan {a.plan}: completed runs: {total} / {planned}")
    print(f"{'arm':22s} " + " ".join(f"{s[:7]:>7s}" for s in SCENARIOS) + "   total (done/planned)")
    for arm in ARMS:
        counts = [len(cells.get((arm, s), ())) for s in SCENARIOS]
        if a.plan == "v2" and not any(k[0] == arm for k in plan):
            continue
        print(f"{arm:22s} " + " ".join(f"{c:>3d}/{plan.get((arm, s), 0):<3d}" for c, s in zip(counts, SCENARIOS)) + f"   {sum(counts)}/{sum(v for k, v in plan.items() if k[0] == arm)}")
    print(f"\nheartbeat: raw results last written {age(raw)}; progress log last written {age(log)}")
    try:   # last progress line, if the log is not momentarily locked by its writer
        lines = log.read_text(errors="replace").splitlines()
        print("last progress line (arm start/end markers only): " +
              next((x for x in reversed(lines) if " arm " in x), "none yet"))
    except OSError:
        print("progress log is locked by its writer right now (normal)")
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command",
                              "Get-CimInstance Win32_Process | ? { $_.Name -match '^(python|powershell|pwsh)\\.exe$' } | "
                              "% { $_.CommandLine }"], capture_output=True, text=True, timeout=30).stdout
        lines = [x for x in out.splitlines() if re.search(DRIVER, x) and "Get-CimInstance" not in x]
        arms_running = sorted({x.split("--arm")[1].split()[0] for x in lines if "--arm" in x})
        print(f"driver running: {bool(lines)}; runner currently on arm: {arms_running or 'none'}")
    except (OSError, subprocess.SubprocessError):
        print("could not list processes")
    for name, url, key in (("evaluator", "http://localhost:8200/health", "ok"), ("brain", "http://localhost:8000/status", "brain")):
        try:
            j = httpx.get(url, timeout=3).json()
            h = str((j.get("calibration") or {}).get("data_hash", ""))[:12]
            print(f"{name}: up" + (f" (brain={j.get('brain')}, mode={j.get('mode')}, models={MODEL_HASHES.get(h, 'unknown models, data hash ' + h)})" if name == "brain" else ""))
        except (httpx.HTTPError, ValueError):
            print(f"{name}: not answering (expected for the brain during the no_action arm or between arms)")


if __name__ == "__main__":
    main()
