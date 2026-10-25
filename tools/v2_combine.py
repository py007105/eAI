"""Build the evaluated v2 set: the valid original rows plus the Amendment 8 re-run rows, verbatim, in one derived file. Read-only on the inputs.

    python tools/v2_combine.py --raw .../benchmark_v2_raw.jsonl --rerun .../benchmark_v2_rerun_raw.jsonl --invalid .../invalid_rows.json --out .../benchmark_v2_evaluated.jsonl

Original rows listed in the sidecar (matched on arm, scenario, seed and run end time) are left out; nothing is edited or deleted in the inputs. The output
is derived and can be regenerated at any time; the criteria script, the status script and the renderer read it with their existing --raw flags.
Exits non-zero if the same (arm, scenario, seed) would appear twice.
"""
import argparse
import json
import sys
from pathlib import Path


def combine(raw_lines, rerun_lines, invalid):
    bad = {(i["arm"], i["scenario"], i["seed"], i["t_end"]) for i in invalid}
    out, seen, dropped = [], set(), 0
    for src, lines in (("original", raw_lines), ("rerun", rerun_lines)):
        for x in lines:
            if not x.strip():
                continue
            r = json.loads(x)
            key = (r["arm"], r["scenario"], r["seed"])
            if src == "original" and key + (r["score"]["t_end"],) in bad:
                dropped += 1
                continue
            if key in seen:
                raise ValueError(f"duplicate row {key} ({src})")
            seen.add(key)
            out.append(x)
    return out, dropped


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", required=True)
    ap.add_argument("--rerun", required=True)
    ap.add_argument("--invalid", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    rerun = Path(a.rerun).read_text(encoding="utf-8").splitlines() if Path(a.rerun).exists() else []
    invalid = json.loads(Path(a.invalid).read_text(encoding="utf-8"))["invalid"]
    try:
        out, dropped = combine(Path(a.raw).read_text(encoding="utf-8").splitlines(), rerun, invalid)
    except ValueError as e:
        sys.exit(str(e))
    Path(a.out).write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"evaluated set: {len(out)} rows = {len(out) - sum(1 for x in rerun if x.strip())} valid original + {sum(1 for x in rerun if x.strip())} re-run; "
          f"{dropped} invalid originals left out (still in {Path(a.raw).name})")


if __name__ == "__main__":
    main()
