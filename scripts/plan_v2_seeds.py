"""Plan the v2 seeds (G3): fresh TRAINING jobs from the unused training block, and the fresh EVALUATION seeds. Deterministic, no randomness of its own.

    python scripts/plan_v2_seeds.py [--training-runs D:/eAI/eAI-workspace/eAI/data/runs] [--out-json docs/v2_seed_plan.json] [--out-md docs/v2_seed_plan.md]

The evaluator derives the target service and the surge intensity from the seed alone: `random.Random(seed).choice(targets)` for the target (the first draw in
`evaluator/main.py::start`) and `random.Random(seed).choice([25, 40])` for the surge intensity (the first draw in `evaluator/scenarios.py::inject`, on a fresh
generator in `_execute`). This script simulates those draws to CHOOSE seeds for fresh training data with the coverage v1 lacked, and to REPORT what the evaluation
seeds will contain. The simulation is validated against every recorded run (the 225 benchmark rows and the training runs) before it is trusted
(tests/test_plan_v2_seeds.py and the check in main). Choosing training seeds this way uses no benchmark results and no model output.
"""
import argparse
import json
import random
from collections import Counter
from pathlib import Path

SERVICES = ["web", "orders", "payments", "inventory"]
SCENARIOS = ["crash", "latency", "error_spike", "memory_leak", "disk_fill", "bad_deploy", "cpu_burn", "traffic_surge", "good_deploy"]
TARGETS = {s: SERVICES for s in SCENARIOS}
TARGETS["traffic_surge"] = ["web"]
TRAIN_BLOCK = range(1800, 2000)          # unused training-block seeds (v1 training used 1000-1707; 2000+ is the smoke block)
EVAL_SEED0 = 200                         # v1 benchmark used 100-148
FAULTS = ["crash", "latency", "error_spike", "memory_leak", "disk_fill", "bad_deploy", "cpu_burn"]
HEALTHY = ["traffic_surge", "good_deploy"]


def sim_target(scenario, seed):
    return random.Random(seed).choice(TARGETS[scenario])


def sim_surge_level(seed):
    return random.Random(seed).choice([25, 40])


def training_wishlist():
    """(scenario, wanted target, wanted surge level or None). cpu_burn is never used for training (it is the unseen fault)."""
    w = [("traffic_surge", "web", lv) for lv in (25, 40) for _ in range(6)]
    w += [("good_deploy", t, None) for t in ("web", "orders", "inventory", "payments", "orders", "inventory")]
    w += [("crash", "orders", None)] * 3 + [("crash", "payments", None)] * 3
    w += [("bad_deploy", "payments", None), ("bad_deploy", "web", None), ("latency", "inventory", None), ("latency", "web", None),
          ("error_spike", "web", None), ("error_spike", "orders", None), ("memory_leak", "orders", None), ("memory_leak", "payments", None),
          ("disk_fill", "orders", None), ("disk_fill", "payments", None)]
    return w


def plan_training(block=TRAIN_BLOCK):
    used, jobs = set(), []
    for scen, tgt, lvl in training_wishlist():
        for seed in block:
            if seed in used:
                continue
            if sim_target(scen, seed) == tgt and (lvl is None or sim_surge_level(seed) == lvl):
                used.add(seed)
                jobs.append({"scenario": scen, "seed": seed, "target": tgt, "surge_level": lvl})
                break
        else:
            raise RuntimeError(f"no free seed in the block gives {scen} on {tgt} level {lvl}")
    return jobs


def capture_seeds(block=range(3600, 3700), per_level=6):
    """Seeds for the read-only surge capture: `per_level` seeds for each surge intensity, from the 3600-3699 block."""
    out = {25: [], 40: []}
    for seed in block:
        lv = sim_surge_level(seed)
        if len(out[lv]) < per_level:
            out[lv].append(seed)
    return out[25] + out[40]


def eval_seeds(seed0=EVAL_SEED0):
    """Reduced v2 evaluation plan (Amendment 4): per arm, the (scenario, rep, seed) runs, seeds built exactly as scripts/run_benchmark.py builds them
    (seed0 + 10*rep + SCENARIOS index). Autopilot: 12 reps of each healthy scenario and 3 reps of each fault scenario (including the unseen cpu_burn);
    threshold_restart: the same 12+12 healthy seeds; ask-first: 4 reps of each healthy scenario and 3 reps of the six supported faults."""
    sup = [s for s in FAULTS if s != "cpu_burn"]
    spec = {"eternalai_autopilot": {**{s: 12 for s in HEALTHY}, **{s: 3 for s in FAULTS}},
            "threshold_restart": {s: 12 for s in HEALTHY},
            "eternalai_ask_first": {**{s: 4 for s in HEALTHY}, **{s: 3 for s in sup}}}
    out = []
    for arm, per in spec.items():
        for scen in SCENARIOS:
            for rep in range(per.get(scen, 0)):
                seed = seed0 + 10 * rep + SCENARIOS.index(scen)
                out.append({"arm": arm, "scenario": scen, "rep": rep, "seed": seed, "target": sim_target(scen, seed),
                            "surge_level": sim_surge_level(seed) if scen == "traffic_surge" else None})
    return out


def validate(benchmark_rows, training_truths):
    """Return (checked, mismatches) of the simulation against recorded runs."""
    bad, n = [], 0
    for kind, runs in (("benchmark", benchmark_rows), ("training", training_truths)):
        for r in runs:
            n += 1
            wrong_target = sim_target(r["scenario"], r["seed"]) != r["target"]
            wrong_level = r["scenario"] == "traffic_surge" and sim_surge_level(r["seed"]) != r["params"]["extra_rps_per_thread"]
            if wrong_target or wrong_level:
                bad.append((kind, r["scenario"], r["seed"]))
    return n, bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--training-runs", default="D:/eAI/eAI-workspace/eAI/data/runs")
    ap.add_argument("--benchmark-raw", default="results/benchmark-v1/benchmark_raw.jsonl")
    ap.add_argument("--out-json", default="docs/v2_seed_plan.json")
    ap.add_argument("--out-md", default="docs/v2_seed_plan.md")
    a = ap.parse_args()
    rows = [json.loads(line) for line in Path(a.benchmark_raw).read_text().splitlines()]
    truths = [json.loads(f.read_text()) for f in Path(a.training_runs).glob("*.json") if f.name != "EXCLUDED.json"]
    n, bad = validate(rows, truths)
    assert not bad, f"the seed simulation disagrees with recorded runs: {bad[:5]}"
    train, ev = plan_training(), eval_seeds()
    Path(a.out_json).write_text(json.dumps({"validated_against": n, "training_jobs": train, "evaluation_seeds": ev, "capture_seeds": capture_seeds()}, indent=1), encoding="utf-8")
    ct = Counter((j["scenario"], j["target"], j["surge_level"]) for j in train)
    uniq = {(e["scenario"], e["rep"], e["seed"]): e for e in ev}.values()        # arms share seeds; describe each seed once
    ce = Counter((e["scenario"], e["target"], e["surge_level"]) for e in uniq)
    per_arm = Counter(e["arm"] for e in ev)
    md = ["# v2 seed plan (generated by `scripts/plan_v2_seeds.py`)\n",
          f"The evaluator derives target and surge intensity from the seed alone. The simulation was checked against {n} recorded runs (225 benchmark rows and the training runs) with 0 mismatches before use.\n",
          f"## Fresh training jobs: {len(train)} runs from the unused block {TRAIN_BLOCK.start}-{TRAIN_BLOCK.stop - 1}\n",
          "| scenario | target | surge level | runs |\n|---|---|---|---|"]
    md += [f"| {k[0]} | {k[1]} | {k[2] or '-'} | {v} |" for k, v in sorted(ct.items(), key=lambda kv: (kv[0][0], kv[0][1], str(kv[0][2])))]
    md += ["", "Jobs (`scenario:seed`): " + " ".join(f"{j['scenario']}:{j['seed']}" for j in train), "",
           f"## Evaluation seeds (reduced plan, Amendment 4): seed0 = {EVAL_SEED0}; {len(ev)} runs in total: " + ", ".join(f"{k} {v}" for k, v in per_arm.items()) + "\n",
           f"Seeds {min(e['seed'] for e in ev)}-{max(e['seed'] for e in ev)}; {len(list(uniq))} distinct seeds (the arms share seeds, so they are paired). What the seeds contain (decided by the seed, not chosen):\n",
           "| scenario | target | surge level | seeds |\n|---|---|---|---|"]
    md += [f"| {k[0]} | {k[1]} | {k[2] or '-'} | {v} |" for k, v in sorted(ce.items(), key=lambda kv: (kv[0][0], kv[0][1], str(kv[0][2])))]
    md += ["", "## Read-only surge capture seeds (3600-3699): " + " ".join(f"{s}(level {sim_surge_level(s)})" for s in capture_seeds()),
           "Done: the first six (level 25). Remaining six (all level 40) are used by Stage 0 (telemetry condition experiment): 3604 3608 3614 3620 3621 3624."]
    Path(a.out_md).write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
