"""Stage 1 of the v2 plan (Amendment 4 sections J-E4 and R): collect the 34 fresh training runs under the chosen telemetry condition.

    python tools/stage1_collect.py [--out ml/data/runs_v2] [--warmup-min 45] [--gap-min 60] [--min-free-gb 1.0]

Resumable (state in <out>/_stage1_state.json; every run is a separate atomic file, see tools/safe_collect.py). Steps:
  1. the stack must already be up under the chosen condition (tools/v2_stack.ps1 does that); the apps' age is the time since it started, and the
     collector waits until at least `--warmup-min` minutes of continuous load have passed since `warmup_started`;
  2. batch 1 = the first half of the jobs, then the stack is LEFT RUNNING for `--gap-min` minutes (container ages and prior load keep growing);
  3. batch 2 = the second half.
The job list comes from docs/v2_seed_plan.json (training_jobs), shuffled with a fixed seed so both batches mix scenarios. No brain runs during collection.
"""
import argparse
import json
import os
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import memguard  # noqa: E402
import safe_collect as sc  # noqa: E402

PLAN = Path(os.getenv("V2_SEED_PLAN", "D:/eAI/eAI-docs/docs/v2_seed_plan.json"))


def now_s():
    return time.time()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="ml/data/runs_v2")
    ap.add_argument("--warmup-min", type=float, default=45.0)
    ap.add_argument("--gap-min", type=float, default=60.0)
    ap.add_argument("--min-free-gb", type=float, default=1.0)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    state_f = out / "_stage1_state.json"
    state = json.loads(state_f.read_text()) if state_f.exists() else {}
    save = lambda: sc.atomic_write_text(state_f, json.dumps(state))        # noqa: E731
    if "warmup_started" not in state:
        state["warmup_started"] = now_s()
        save()
    jobs = [(j["scenario"], j["seed"]) for j in json.loads(PLAN.read_text())["training_jobs"]]
    random.Random(2026).shuffle(jobs)
    half = len(jobs) // 2
    batches = [jobs[:half], jobs[half:]]

    from engine import config
    from engine.collector import Prom
    prom = Prom()

    wait = state["warmup_started"] + a.warmup_min * 60 - now_s()
    if wait > 0:
        print(f"[{time.strftime('%H:%M:%S')}] warm-up: {wait / 60:.1f} min of continuous load still to go", flush=True)
        time.sleep(wait)
    for i, batch in enumerate(batches, 1):
        if i == 2 and "batch1_done" in state:
            gap = state["batch1_done"] + a.gap_min * 60 - now_s()
            if gap > 0:
                print(f"[{time.strftime('%H:%M:%S')}] gap: leaving the stack running for {gap / 60:.1f} more min", flush=True)
                time.sleep(gap)
        n = 0
        for scen, seed in batch:
            n += sc.collect_one(scen, seed, out, prom, config.SERVICES, a.min_free_gb)
        if f"batch{i}_done" not in state:        # a resume must not move the original completion time (the gap is measured from it)
            state[f"batch{i}_done"] = now_s()
            save()
        print(f"[{time.strftime('%H:%M:%S')}] batch {i} done ({n} new runs)", flush=True)
    print("stage 1 collection complete", flush=True)


if __name__ == "__main__":
    main()
