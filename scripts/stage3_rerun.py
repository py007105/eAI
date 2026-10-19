"""Stage 3 re-run driver (Amendment 8): re-runs the cells made invalid by the stock-out, one run at a time, behind the inventory stock gate.

    python scripts/stage3_rerun.py --repo D:/eAI/eAI-workspace/eAI --jobs results/benchmark-v2/invalid_rows.json [--dry-run]

Reads the job list written by scripts/v2_validity_mark.py (order = the pre-registered order). Per job: stock gate (restock if needed, verify; abort WITHOUT starting
the run if that fails), then ONE `scripts/run_benchmark.py` invocation for exactly that (arm, scenario, seed), so the system code and the run logic are untouched.
The brain is (re)started once per arm segment, as stage3_eval did; the per-run state reset inside run_benchmark is unchanged. After the run the row gets a
`stock` entry (per-SKU stock before the gate, after the restock, and after the run) and the same record is appended to stock_log.jsonl.
Resumable: a finished (arm, scenario, seed) in the re-run file is skipped. Results go to their own file; the original v2 file is never written.
"""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import stock_gate  # noqa: E402

SCENARIOS = ["crash", "latency", "error_spike", "memory_leak", "disk_fill", "bad_deploy", "cpu_burn", "traffic_surge", "good_deploy"]
ARMS = {"threshold_restart": ("threshold_restart", "autopilot"), "eternalai_ask_first": ("eternalai", "ask-first"), "eternalai_autopilot": ("eternalai", "autopilot")}


def finished(raw):
    done = set()
    if Path(raw).exists():
        for x in Path(raw).read_text(encoding="utf-8").splitlines():
            if x.strip():
                r = json.loads(x)
                done.add((r["arm"], r["scenario"], r["seed"]))
    return done


def annotate(raw, key, stock):
    """Add the stock record to the row for `key` (rewrite the file atomically; only this file, only this row)."""
    p = Path(raw)
    lines, hit = [], False
    for x in p.read_text(encoding="utf-8").splitlines():
        if x.strip():
            r = json.loads(x)
            if (r["arm"], r["scenario"], r["seed"]) == key and "stock" not in r:
                r["stock"], hit = stock, True
            x = json.dumps(r)
        lines.append(x)
    tmp = p.with_suffix(".tmp")
    tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.replace(tmp, p)
    return hit


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True, help="the system tree (run_benchmark.py is run from here)")
    ap.add_argument("--jobs", required=True)
    ap.add_argument("--raw", default="results/benchmark-v2/benchmark_v2_rerun_raw.jsonl")
    ap.add_argument("--stock-log", default="results/benchmark-v2/stock_log.jsonl")
    ap.add_argument("--models-label", default="models-v2 (frozen; see docs/MODEL_CARD.md)")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    repo = Path(a.repo)
    jobs = json.loads(Path(a.jobs).read_text(encoding="utf-8"))["jobs"]
    raw, slog = repo / a.raw, repo / a.stock_log
    sys.path[:0] = [str(repo / "scripts"), str(repo / "models")]
    os.chdir(repo)
    import run_benchmark as rb      # start/stop of the brain and the benchmark token only; runs go through its CLI
    token = rb.benchmark_token()
    current = None
    try:
        for n, j in enumerate(jobs, 1):
            key = (j["arm"], j["scenario"], j["seed"])
            if key in finished(raw):
                continue
            print(f"== job {n}/{len(jobs)}: {j['segment']} {j['arm']} {j['scenario']} seed {j['seed']} ({j['kind']}, replaces {j['replaces_seed']})", flush=True)
            if a.dry_run:
                continue
            if j["arm"] != current:
                if current is not None:
                    rb.stop_brain()
                brain, mode = ARMS[j["arm"]]
                rb.start_brain(brain, mode, token)
                current = j["arm"]
            try:
                rec = stock_gate.gate()
            except stock_gate.GateError as e:
                sys.exit(f"STOP: stock gate failed before job {n}; the run was NOT started: {e}")
            print(f"   stock before {rec['before']} restocked {rec['restocked']} after_restock {rec['after_restock']}", flush=True)
            seed0 = j["seed"] - SCENARIOS.index(j["scenario"])
            cmd = [sys.executable, "-u", "scripts/run_benchmark.py", "--arm", j["arm"], "--reps", "1", "--seed0", str(seed0), "--raw", a.raw,
                   "--models-label", a.models_label, "--scenarios", j["scenario"]]
            rc = subprocess.run(cmd).returncode
            try:
                rec["after_run"] = stock_gate.read_stock()
            except stock_gate.GateError as e:
                rec["after_run"] = f"unreadable: {e}"
            rec["job"] = j
            rec["rc"] = rc
            with slog.open("a", encoding="utf-8") as f:
                f.write(json.dumps(rec) + "\n")
            if key in finished(raw):
                annotate(raw, key, {k: rec[k] for k in ("before", "restocked", "after_restock", "after_run", "t", "threshold", "seed_level") if k in rec}
                         | {"brain_incidents_in_restock_window": rec.get("brain_incidents_in_restock_window")})
            else:
                sys.exit(f"STOP: job {n} produced no result row (run_benchmark exit {rc}); rerun this command to retry the same job")
        print("re-run complete", flush=True)
    finally:
        if current is not None and not a.dry_run:
            rb.stop_brain()


if __name__ == "__main__":
    main()
