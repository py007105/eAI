"""(fault, target service) coverage: training runs vs benchmark runs, and where the autopilot's FIRST incident abstained.

    python tools/coverage_table.py --runs D:/eAI/eAI-workspace/eAI/data/runs --raw results/benchmark-v1/benchmark_raw.jsonl --out docs/postmortems/coverage-training-vs-benchmark.md
"""
import argparse
import json
from collections import Counter
from pathlib import Path

import pandas as pd

ap = argparse.ArgumentParser()
ap.add_argument("--runs", required=True)
ap.add_argument("--raw", required=True)
ap.add_argument("--out", required=True)
a = ap.parse_args()
train = Counter()
for f in Path(a.runs).glob("*.json"):
    if f.name != "EXCLUDED.json":
        t = json.loads(f.read_text())
        train[(t["scenario"], t["target"])] += 1
rows = [json.loads(line) for line in Path(a.raw).read_text().splitlines()]
bench = Counter((r["scenario"], r["target"]) for r in rows if r["arm"] == "no_action")
first_abs = Counter((r["scenario"], r["target"]) for r in rows if r["arm"] == "eternalai_autopilot" and r.get("incidents") and r["incidents"][0]["abstained"])
auto = Counter((r["scenario"], r["target"]) for r in rows if r["arm"] == "eternalai_autopilot")
tab = pd.DataFrame([{"fault": k[0], "target": k[1], "training runs": train.get(k, 0), "benchmark runs per arm": bench.get(k, 0),
                     "autopilot first incident abstained": f"{first_abs.get(k, 0)}/{auto.get(k, 0)}"} for k in sorted(set(train) | set(bench))])
txt = ["# (fault, target) coverage: training vs benchmark v1\n",
       "Training runs counted from `ml/data/runs/*.json` (72, including those excluded from fitting); benchmark runs are per arm (paired seeds give every arm the same targets). "
       "'First incident abstained' uses the autopilot arm's first recorded incident in each run, including healthy scenarios.\n", tab.to_markdown(index=False), ""]
Path(a.out).write_text("\n".join(txt), encoding="utf-8")
print("\n".join(txt))
