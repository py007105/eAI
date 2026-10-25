"""Stage 3 driver: the pre-registered v2 evaluation (docs/EVALUATION_PLAN.md, Amendment 4 section M), in priority order, resumable.

    python tools/stage3_eval.py [--raw results/benchmark-v2/benchmark_v2_raw.jsonl] [--models-label "models-v2 ..."] [--seed0 200] [--dry-run]

Each line below is one `run_benchmark.py` invocation (finished (arm, scenario, seed) rows are skipped, so a restart repeats nothing). The seeds are
seed0 + 10*repetition + scenario index, so the arms share seeds (paired). The stack must already be up under the chosen telemetry condition (tools/v2_stack.ps1).
"""
import argparse
import subprocess
import sys
from pathlib import Path

HEALTHY = ["traffic_surge", "good_deploy"]
SUPPORTED = ["crash", "latency", "error_spike", "memory_leak", "disk_fill", "bad_deploy"]
PLAN = [  # (priority, arm, scenarios, repetitions)
    ("P1", "eternalai_autopilot", HEALTHY, 12),
    ("P1", "threshold_restart", HEALTHY, 12),
    ("P1/P2", "eternalai_ask_first", HEALTHY, 4),
    ("P2", "eternalai_ask_first", SUPPORTED, 3),
    ("P3", "eternalai_autopilot", SUPPORTED + ["cpu_burn"], 3),
]


def commands(raw, models_label, seed0, python=sys.executable):
    for prio, arm, scen, reps in PLAN:
        yield prio, [python, "-u", "tools/run_benchmark.py", "--arm", arm, "--manage-stack", "--reps", str(reps), "--seed0", str(seed0),
                     "--raw", raw, "--models-label", models_label, "--scenarios", *scen]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default="results/benchmark-v2/benchmark_v2_raw.jsonl")
    ap.add_argument("--models-label", default="models-v2 (frozen; see docs/MODEL_CARD.md)")
    ap.add_argument("--seed0", type=int, default=200)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    Path(a.raw).parent.mkdir(parents=True, exist_ok=True)
    for prio, cmd in commands(a.raw, a.models_label, a.seed0):
        print(f"== {prio}: {' '.join(cmd[3:])}", flush=True)
        if not a.dry_run:
            rc = subprocess.run(cmd).returncode
            if rc:
                sys.exit(f"stage 3 stopped: {prio} invocation exited with {rc}; rerun the same command to resume")
    print("stage 3 complete", flush=True)


if __name__ == "__main__":
    main()
