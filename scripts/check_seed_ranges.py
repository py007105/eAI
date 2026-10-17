"""Check that the seed ranges planned for the post-benchmark checks overlap no seed already used.

    python scripts/check_seed_ranges.py [--runs D:/eAI/eAI-workspace/eAI/data/runs] [--smoke PATH] [--out docs/results/seed_check.md]

Used seeds: training (the `seed` field of every data/runs/*.json), benchmark v1 (100 + 10*rep + scenario index, 5 reps x 9 scenarios),
the two disclosed smoke seeds in docs/EVALUATION_PLAN.md section 0 (100, 104), the seeds in the benchmark smoke file, and the reserved blocks
the code itself uses (training 1000-1999, smoke/benchmark-smoke 2000-2999). The evaluator's own result volume is not read here (no Docker).
Exit code 1 if any planned range overlaps.
"""
import argparse
import json
import sys
from pathlib import Path

PLANNED = {"forecast check": range(3000, 3005), "forecast smoke": range(3900, 3902), "live LLM check": range(3500, 3505)}
RESERVED = {"training block (collect_runs default 1000+)": range(1000, 2000), "smoke block (run_benchmark --smoke uses >= 2000)": range(2000, 3000)}


def used_seeds(runs_dir, smoke_file):
    used = {}
    for js in Path(runs_dir).glob("*.json"):
        if js.name != "EXCLUDED.json":
            used.setdefault(json.loads(js.read_text())["seed"], []).append("training run " + js.stem)
    for rep in range(5):
        for i in range(9):
            used.setdefault(100 + 10 * rep + i, []).append("benchmark v1")
    for s in (100, 104):
        used.setdefault(s, []).append("disclosed smoke (plan section 0)")
    if smoke_file and Path(smoke_file).exists():
        for line in Path(smoke_file).read_text().splitlines():
            used.setdefault(json.loads(line)["seed"], []).append("benchmark smoke file")
    return used


def check(used, planned=PLANNED, reserved=RESERVED):
    problems = []
    for name, rng in planned.items():
        for s in rng:
            for why in used.get(s, []):
                problems.append(f"{name}: seed {s} already used by {why}")
            for rname, rr in reserved.items():
                if s in rr:
                    problems.append(f"{name}: seed {s} falls in the {rname}")
    names = list(planned)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            both = set(planned[a]) & set(planned[b])
            if both:
                problems.append(f"{a} and {b} overlap on {sorted(both)}")
    return problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", default="data/runs")
    ap.add_argument("--smoke", default="docs/results/benchmark_smoke.jsonl")
    ap.add_argument("--out")
    a = ap.parse_args()
    used = used_seeds(a.runs, a.smoke)
    problems = check(used)
    lines = ["# Seed range check", "", f"Seeds already used: {len(used)} distinct (min {min(used)}, max {max(used)}).", "",
             "Planned: " + "; ".join(f"{k} {r.start}-{r.stop - 1}" for k, r in PLANNED.items()), "",
             "Overlaps: " + ("none" if not problems else ""), *[f"- {p}" for p in problems]]
    out = "\n".join(lines) + "\n"
    print(out)
    if a.out:
        Path(a.out).write_text(out, encoding="utf-8")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
