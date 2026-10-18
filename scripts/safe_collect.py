"""Retry-safe collector for FRESH TRAINING runs (tooling). Same output files as models/collect_runs.py, but resumable and atomic, with a memory guard.

    python scripts/safe_collect.py --jobs crash:1824 traffic_surge:1801 ... --out data/runs_v2 [--min-free-gb 1.0]

- Resumable: a run counts as done only when its `<scenario>_<seed>.json` exists; that file is written LAST, so a kill leaves at most one unfinished run and
  never a half-written one (each file is written to a temporary name and renamed).
- Memory guard: before each run it waits (and logs) until free RAM is at least `--min-free-gb`; it never starts a run under memory pressure.
- Seeds must lie in the unused training block 1800-1999 (v1 training used 1000-1707; 2000+ is the smoke block).
- It records the age of every container when the run starts (`stack_ages_min` in the truth JSON), so data can be checked for realistic container ages.
The evaluator reveals the truth only for OFFLINE training use, exactly as models/collect_runs.py does; nothing here reaches the brain.
"""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import memguard  # noqa: E402

EV = "http://localhost:8200"
TIMEOUT = {"memory_leak": 100, "disk_fill": 80}
DEFAULT_TIMEOUT = 45


def atomic_write_text(path: Path, text: str):
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def parse_jobs(jobs):
    out = []
    for j in jobs:
        scen, seed = j.split(":")
        out.append((scen, int(seed)))
    if not all(1800 <= s <= 1999 for _, s in out):
        raise SystemExit("fresh training seeds must lie in the unused block 1800-1999")
    return out


def stack_ages_min(now=None):
    """Age in minutes of each running container of the compose project (empty dict if docker is not reachable)."""
    try:
        out = subprocess.run(["docker", "ps", "--format", "{{.Names}}|{{.RunningFor}}"], capture_output=True, text=True, timeout=20).stdout
    except (OSError, subprocess.SubprocessError):
        return {}
    return {line.split("|")[0]: line.split("|")[1] for line in out.splitlines() if "|" in line}


def collect_one(scen, seed, out: Path, prom, services, min_free_gb, log=print):
    tag = out / f"{scen}_{seed}"
    if tag.with_suffix(".json").exists():
        return False
    memguard.wait_for_memory(min_free_gb, log=log)
    ages = stack_ages_min()
    r = httpx.post(f"{EV}/runs", json={"scenario": scen, "seed": seed, "timeout_s": TIMEOUT.get(scen, DEFAULT_TIMEOUT), "healthy_s": 60}, timeout=20)
    r.raise_for_status()
    rid = r.json()["run_id"]
    while httpx.get(f"{EV}/runs/{rid}/status", timeout=10).json()["state"] == "running":
        time.sleep(5)
    rev = httpx.get(f"{EV}/runs/{rid}/reveal", timeout=10)
    if rev.status_code != 200:
        err = httpx.get(f"{EV}/runs/{rid}/status", timeout=10).json().get("error", "unknown")
        log(f"{scen} seed {seed}: run failed ({err}); rerun the same command to retry this seed", flush=True)
        return False
    truth = rev.json()["truth"]
    t0 = truth["t_inject"]
    end = rev.json()["score"].get("t_end") or (time.time() - 12)
    span_end = min(t0 + 100, end)
    import pandas as pd
    frames = {s: prom.signals(s, seconds=int(span_end - (t0 - 240)), end=span_end) for s in services}
    atomic_write_text(tag.with_suffix(".csv"), pd.concat(frames, names=["service", "t"]).to_csv())
    truth["stack_ages"] = ages
    atomic_write_text(tag.with_suffix(".json"), json.dumps(truth))      # written last: its existence marks the run as done
    log(f"saved {tag.name} target={truth['target']}", flush=True)
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", nargs="+", required=True, help="scenario:seed pairs")
    ap.add_argument("--out", required=True)
    ap.add_argument("--min-free-gb", type=float, default=1.0)
    a = ap.parse_args()
    from eternalai import config
    from eternalai.collector import Prom
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    prom, n = Prom(), 0
    for scen, seed in parse_jobs(a.jobs):
        n += collect_one(scen, seed, out, prom, config.SERVICES, a.min_free_gb)
    print(f"done: {n} new runs", flush=True)


if __name__ == "__main__":
    main()
