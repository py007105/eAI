"""Check that the seed ranges planned for the post-benchmark checks overlap no seed already used.

    python scripts/check_seed_ranges.py [--runs D:/eAI/eAI-workspace/eAI/data/runs] [--smoke PATH] [--out docs/results/seed_check.md]

Used seeds: training (the `seed` field of every data/runs/*.json), benchmark v1 (100 + 10*rep + scenario index, 5 reps x 9 scenarios),
the two disclosed smoke seeds in docs/EVALUATION_PLAN.md section 0 (100, 104), the seeds in the benchmark smoke file, and the reserved blocks
the code itself uses (training 1000-1999, smoke/benchmark-smoke 2000-2999). With --truth-zip the seeds of every run in the exported evaluator volume are included.
Exit code 1 if any planned range overlaps.
"""
import argparse
import json
import sys
from pathlib import Path

PLANNED = {"forecast check": range(3000, 3005), "forecast smoke": range(3900, 3902), "live LLM check": range(3500, 3505)}
RESERVED = {"training block (collect_runs default 1000+)": range(1000, 2000), "smoke block (run_benchmark --smoke uses >= 2000)": range(2000, 3000)}


def used_seeds(runs_dir, smoke_file, truth_zip=None):
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
    if truth_zip and Path(truth_zip).exists():
        import zipfile
        z = zipfile.ZipFile(truth_zip)
        for name in z.namelist():
            if not name.startswith("truth/"):
                continue
            for line in z.read(name).decode(errors="replace").splitlines() if name.endswith(".jsonl") else [z.read(name).decode(errors="replace")]:
                try:
                    d = json.loads(line)
                except ValueError:
                    continue
                s = d.get("seed", (d.get("truth") or {}).get("seed")) if isinstance(d, dict) else None
                if isinstance(s, int):
                    used.setdefault(s, []).append("evaluator truth volume record")
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
    ap.add_argument("--plan-json", help="docs/v2_seed_plan.json: also check every fresh training seed and every v2 evaluation seed")
    ap.add_argument("--truth-zip", help="results/benchmark-v1/truth_and_evidence.zip: seeds of every run the evaluator ever recorded")
    ap.add_argument("--out")
    a = ap.parse_args()
    used = used_seeds(a.runs, a.smoke, a.truth_zip)
    planned = dict(PLANNED)
    reserved = dict(RESERVED)
    if a.plan_json:
        plan = json.loads(Path(a.plan_json).read_text())
        planned["v2 fresh training seeds"] = [j["seed"] for j in plan["training_jobs"]]
        planned["v2 evaluation seeds"] = [e["seed"] for e in plan["evaluation_seeds"]]
        reserved.pop("training block (collect_runs default 1000+)")        # the fresh training seeds are SUPPOSED to be in the unused part of that block
        reserved["used training seeds 1000-1799 (v1)"] = range(1000, 1800)
    problems = check(used, planned, reserved)
    lines = ["# Seed range check", "", f"Seeds already used: {len(used)} distinct (min {min(used)}, max {max(used)}).", "",
             "Planned: " + "; ".join(f"{k} {min(r)}-{max(r)} ({len(list(r))} seeds)" for k, r in planned.items()), "",
             "Overlaps: " + ("none" if not problems else ""), *[f"- {p}" for p in problems]]
    out = "\n".join(lines) + "\n"
    print(out)
    if a.out:
        Path(a.out).write_text(out, encoding="utf-8")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
