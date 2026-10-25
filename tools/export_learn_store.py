"""Export the learn store as training rows (plan §9.7): dataset-A-style (root features + human label) and dataset-C-style
(fault, fix, verified outcome) CSVs.

    python tools/export_learn_store.py --db runtime/eternalai.db --out runtime/learn-export

Rows without human feedback have an empty label: they are never used as ground truth by themselves.
"""
import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine.store import LearnStore  # noqa: E402


def write(rows, path):
    first = [k for k in ("incident_id", "root", "label", "label_source", "fault", "fault_source", "fix") if any(k in r for r in rows)]
    keys = first + sorted({k for r in rows for k in r} - set(first))
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="runtime/eternalai.db")
    ap.add_argument("--out", default="runtime/learn-export")
    a = ap.parse_args()
    if not Path(a.db).exists():
        sys.exit(f"no learn store at {a.db}")
    s = LearnStore(f"sqlite:///{Path(a.db).as_posix()}")
    a_rows, c_rows = s.training_rows()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    write(a_rows, out / "A_learned_rows.csv")
    write(c_rows, out / "C_learned_outcomes.csv")
    print(f"{len(a_rows)} incident rows ({sum(1 for r in a_rows if r['label'])} human-labelled), {len(c_rows)} outcome rows -> {out}")


if __name__ == "__main__":
    main()
