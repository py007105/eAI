"""Build the v2 training set: copy (never move) the original 72 runs and the fresh v2 runs into one new directory. The sources are not modified.

    python scripts/merge_training_runs.py --old data/runs --new data/runs_v2 --out data/runs_all
"""
import argparse
import shutil
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--old", required=True)
ap.add_argument("--new", required=True)
ap.add_argument("--out", required=True)
a = ap.parse_args()
out = Path(a.out)
out.mkdir(parents=True, exist_ok=True)
seen = {}
for src in (Path(a.old), Path(a.new)):
    for f in sorted(src.iterdir()):
        if f.name.startswith("_") or f.suffix not in (".json", ".csv") or f.name.endswith(".tmp"):
            continue
        if f.name in seen:
            raise SystemExit(f"duplicate file name {f.name} in {src} and {seen[f.name]}")
        seen[f.name] = src
        shutil.copy2(f, out / f.name)
runs = {f.stem for f in out.glob("*.json") if f.name != "EXCLUDED.json"}
missing = [r for r in runs if not (out / f"{r}.csv").exists()]
print(f"{len(runs)} runs copied to {out} ({sum(1 for s in seen.values() if str(s) == a.new)} files from {a.new}); runs without a csv: {missing}")
