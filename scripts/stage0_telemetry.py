"""Stage 0 of the v2 pre-registration (docs/EVALUATION_PLAN.md, Amendment 4, section K): choose the telemetry condition by a rule fixed beforehand.

    python scripts/stage0_telemetry.py run     --out results/stage0 [--seeds 3604 3608 3614 3620 3621 3624]
    python scripts/stage0_telemetry.py decide  --raw results/stage0 --out docs/results/stage0_telemetry.md

Conditions (two surge runs of intensity 40 each, v2 brain in WATCH-ONLY mode, empty LLM keys, non-benchmark seeds):
  T1  Jaeger running with the capped store, apps export traces to it
  T2  Jaeger stopped, apps still export (the v1 benchmark condition)
  T3  Jaeger stopped, OTEL_SDK_DISABLED=true on the apps
Before EVERY run all four apps are recreated under the condition and given 75 s of load-generator traffic, so a run starts from a fresh container and the
memory ratchet seen in the captures (a service keeps its high-water mark) cannot leak from one run, or one condition, into the next.
A condition QUALIFIES when, in both its runs, (i) peak memory during the surge minus the median before it is at most 3 MB for `web` and for `inventory`,
and (ii) the pre-surge median of `web` and of `inventory` lies within 3 MB of the training median (web 66.8 MB, inventory 65.3 MB). The first qualifying
condition in the order T3, T1, T2 is chosen; if none qualifies T3 is chosen and "the exporter does not explain the surge growth" is recorded.
"""
import argparse
import importlib.util
import json
import os
import subprocess
import sys
import time
from pathlib import Path

MAIN = Path(os.getenv("EAI_MAIN_TREE", "D:/eAI/eAI-workspace/eAI"))
DOCKER = r"C:\Program Files\Docker\Docker\resources\bin"
SERVICES = ["web", "orders", "inventory", "payments"]
CONDITIONS = {"T1": {"OTEL_SDK_DISABLED": "false", "jaeger": "up"}, "T2": {"OTEL_SDK_DISABLED": "false", "jaeger": "stopped"},
              "T3": {"OTEL_SDK_DISABLED": "true", "jaeger": "stopped"}}
ORDER_OF_PREFERENCE = ["T3", "T1", "T2"]
TRAINING_MEDIAN_MB = {"web": 66.8, "inventory": 65.3}
LIMIT_MB = 3.0
DEFAULT_SEEDS = [3604, 3608, 3614, 3620, 3621, 3624]       # all level 40; pairs go to T2, T3, T1 in this order of conditions below


# ----------------------------------------------------------------------------------------------- the rule (pure, tested)
def run_facts(run):
    t0, te = run["truth"]["t_inject"], run["score"]["t_end"]
    out = {}
    for s in ("web", "inventory"):
        mem = run["prom"][s]["mem"]
        before = sorted(v for t, v in mem if t0 - 40 <= t < t0 - 5)
        during = [v for t, v in mem if t0 + 5 <= t <= te]
        if not before or not during:
            return None
        med = before[len(before) // 2] / 1e6
        out[s] = {"before_mb": round(med, 1), "peak_mb": round(max(during) / 1e6, 1), "increment_mb": round(max(during) / 1e6 - med, 1)}
    return out


def qualifies(runs_facts):
    """All runs of a condition must satisfy (i) and (ii) for web and inventory."""
    if not runs_facts or any(f is None for f in runs_facts):
        return False
    for f in runs_facts:
        for s in ("web", "inventory"):
            if f[s]["increment_mb"] > LIMIT_MB or abs(f[s]["before_mb"] - TRAINING_MEDIAN_MB[s]) > LIMIT_MB:
                return False
    return True


def decide(facts_by_condition):
    q = {c: qualifies(f) for c, f in facts_by_condition.items()}
    for c in ORDER_OF_PREFERENCE:
        if q.get(c):
            return c, q, "qualifies (first in the order T3, T1, T2)"
    return "T3", q, "no condition qualifies: T3 is used and the finding 'the exporter does not explain the surge growth' is recorded"


# ----------------------------------------------------------------------------------------------- running (needs the stack)
def sh(args, env=None, check=True):
    e = {**os.environ, **(env or {})}
    e["PATH"] = e.get("PATH", "") + os.pathsep + DOCKER
    r = subprocess.run(args, cwd=MAIN, env=e, capture_output=True, text=True)
    if check and r.returncode:
        raise SystemExit(f"command failed: {' '.join(args)}\n{r.stderr[-400:]}")
    return r


def apply_condition(cond):
    c = CONDITIONS[cond]
    env = {"OTEL_SDK_DISABLED": c["OTEL_SDK_DISABLED"]}
    if c["jaeger"] == "up":
        sh(["docker", "compose", "up", "-d", "--no-deps", "jaeger"], env)
    else:
        sh(["docker", "compose", "stop", "jaeger"], env, check=False)
    sh(["docker", "compose", "up", "-d", "--no-deps", "--force-recreate", *SERVICES], env)


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def run_stage(a):
    sc = load("surge_capture", Path(__file__).resolve().parent / "surge_capture.py")
    mg = load("memguard", MAIN / "scripts" / "memguard.py")
    seeds = a.seeds
    assert len(seeds) == 6, "Stage 0 uses exactly the six remaining level-40 capture seeds, two per condition"
    plan = {"T2": seeds[0:2], "T3": seeds[2:4], "T1": seeds[4:6]}
    for cond, pair in plan.items():
        for seed in pair:
            out = Path(a.out) / cond / "raw"
            if (out / f"traffic_surge_{seed}.json").exists():
                continue
            mg.wait_for_memory(2.0)
            print(f"[{time.strftime('%H:%M:%S')}] condition {cond}: recreating the apps", flush=True)
            apply_condition(cond)
            time.sleep(75)
            ns = argparse.Namespace(out=str(out), seeds=[seed])
            sc.collect(ns)
            (Path(a.out) / cond / "condition.json").write_text(json.dumps({"condition": cond, **CONDITIONS[cond]}))


def decide_stage(a):
    facts, rows = {}, []
    for cond in CONDITIONS:
        runs = [json.loads(p.read_text()) for p in sorted((Path(a.raw) / cond / "raw").glob("*.json"))]
        facts[cond] = [run_facts(r) for r in runs] if len(runs) == 2 else []
        for r, f in zip(runs, facts[cond] or [None] * len(runs)):
            if f:
                rows.append({"condition": cond, "seed": r["seed"], "web before MB": f["web"]["before_mb"], "web peak MB": f["web"]["peak_mb"],
                             "web increment MB": f["web"]["increment_mb"], "inventory before MB": f["inventory"]["before_mb"],
                             "inventory peak MB": f["inventory"]["peak_mb"], "inventory increment MB": f["inventory"]["increment_mb"],
                             "incidents in window": sum(1 for i in r["incidents"] if r["truth"]["t_inject"] - 1 <= i["opened_t"] <= r["score"]["t_end"])})
    chosen, q, why = decide(facts)
    import pandas as pd
    text = ["# Stage 0: telemetry condition (pre-registered rule, Amendment 4 section K)\n",
            f"Six surge runs at intensity 40, two per condition, v2 brain in watch-only mode, apps recreated before every run. Training medians: web {TRAINING_MEDIAN_MB['web']} MB, "
            f"inventory {TRAINING_MEDIAN_MB['inventory']} MB; limits: increment and distance at most {LIMIT_MB} MB.\n",
            pd.DataFrame(rows).to_markdown(index=False) if rows else "no runs", "",
            "Qualifies: " + ", ".join(f"{c} = {q.get(c)}" for c in CONDITIONS), "", f"**Chosen: {chosen}** ({why}).", ""]
    Path(a.out).write_text("\n".join(text), encoding="utf-8")
    print("\n".join(text))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--out", required=True)
    r.add_argument("--seeds", type=int, nargs="+", default=DEFAULT_SEEDS)
    d = sub.add_parser("decide")
    d.add_argument("--raw", required=True)
    d.add_argument("--out", required=True)
    a = ap.parse_args()
    run_stage(a) if a.cmd == "run" else decide_stage(a)


if __name__ == "__main__":
    main()
