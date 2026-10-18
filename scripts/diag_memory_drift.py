"""Read-only diagnosis: how does a service's healthy memory depend on container uptime and on the load it has already seen? (seen data; diagnosis only)

    python scripts/diag_memory_drift.py --runs D:/eAI/eAI-workspace/eAI/data/runs --captures results/surge-capture/raw \
        --benchmark-zip results/benchmark-v1/truth_and_evidence.zip [--out docs/postmortems/memory-drift-data.md]

Three views, none of which trains or tunes anything:
  1. the surge captures (non-benchmark seeds): per run and service, pre-surge memory, peak memory and the container's uptime when the run started
     (uptime = injection time minus `app_start_time_seconds`), in the order the runs were made, so a ratchet across consecutive runs is visible;
  2. the training runs: pre-injection memory per service in collection order (time of day of injection), to see whether healthy memory moved while the data was collected;
  3. the v1 benchmark evidence files: the "NN% of limit" in the forecast evidence of every preserved incident, per service, binned by hour. Integer percent only
     (1% is about 2.7 MB), so this shows the level and the trend, not exact megabytes.
"""
import argparse
import json
import re
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

SERVICES = ["web", "orders", "inventory", "payments"]


def captures_table(raw_dir):
    rows = []
    for f in sorted(Path(raw_dir).glob("*.json"), key=lambda p: json.loads(p.read_text())["truth"]["t_inject"]):
        r = json.loads(f.read_text())
        t0, te = r["truth"]["t_inject"], r["score"]["t_end"]
        row = {"seed": r["seed"], "level": r["truth"]["params"]["extra_rps_per_thread"], "run start": pd.to_datetime(t0, unit="s").strftime("%H:%M:%S")}
        for s in SERVICES:
            p = r["prom"][s]
            before = [v for t, v in p["mem"] if t0 - 40 <= t < t0 - 5]
            during = [v for t, v in p["mem"] if t0 + 5 <= t <= te]
            started = [v for t, v in p["start"] if t0 - 40 <= t < t0 - 5]
            row[f"{s} MB before"] = round(float(np.median(before)) / 1e6, 1) if before else None
            row[f"{s} MB peak"] = round(max(during) / 1e6, 1) if during else None
            row[f"{s} uptime min"] = round((t0 - float(np.median(started))) / 60, 1) if started else None
        rows.append(row)
    return pd.DataFrame(rows)


def training_table(runs_dir):
    rows = []
    for js in Path(runs_dir).glob("*.json"):
        if js.name == "EXCLUDED.json":
            continue
        t = json.loads(js.read_text())
        df = pd.read_csv(js.with_suffix(".csv"), index_col=[0, 1])
        row = {"run": js.stem, "t_inject": t["t_inject"]}
        for s in SERVICES:
            if s in df.index.get_level_values(0):
                f = df.loc[s]
                pre = f[(f.index >= t["t_inject"] - 40) & (f.index < t["t_inject"] - 5)].mem_bytes
                row[s] = float(pre.median()) / 1e6 if len(pre) else np.nan
        rows.append(row)
    d = pd.DataFrame(rows).sort_values("t_inject")
    d["hour of collection"] = ((d.t_inject - d.t_inject.min()) // 3600).astype(int)
    return d


def evidence_table(zip_path):
    z = zipfile.ZipFile(zip_path)
    rows = []
    for name in z.namelist():
        if not (name.startswith("evidence/") and name.endswith(".json")):
            continue
        d = json.loads(z.read(name))
        for e in d.get("evidence", []):
            m = re.search(r"(\w+) memory rising .*?(\d+)% of limit", e.get("summary", ""))
            if e.get("tool") == "forecast" and m:
                rows.append({"service": m.group(1), "share_pct": int(m.group(2)), "opened_t": d["opened_t"]})
    d = pd.DataFrame(rows)
    d["hour"] = pd.to_datetime(d.opened_t, unit="s").dt.floor("2h").dt.strftime("%m-%d %H:00 UTC")
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", required=True)
    ap.add_argument("--captures", required=True)
    ap.add_argument("--benchmark-zip", required=True)
    ap.add_argument("--out", default="docs/postmortems/memory-drift-data.md")
    a = ap.parse_args()
    R = ["# Memory versus uptime and prior load (read-only diagnosis on seen data)\n"]
    cap = captures_table(a.captures)
    R.append("## 1. Surge captures, in the order the runs were made (non-benchmark seeds)\n")
    R.append(cap.to_markdown(index=False))
    R.append("\n`uptime min` is the container's age when the run started; a service not targeted by the surge (all but `web`) is not recreated between runs, so its uptime grows by the run length. "
             "Read down a column: a value that rises from run to run without a recreation is memory the process keeps after load (a high-water mark).\n")
    tr = training_table(a.runs)
    R.append("## 2. Training runs: median pre-injection memory (MB) per service, by hour of the collection\n")
    g = tr.groupby("hour of collection")[SERVICES].median().round(1)
    g["runs"] = tr.groupby("hour of collection").size()
    R.append(g.reset_index().to_markdown(index=False))
    R.append(f"\nAll {len(tr)} training runs: median per service " + ", ".join(f"{s} {tr[s].median():.1f} MB (min {tr[s].min():.1f}, max {tr[s].max():.1f})" for s in SERVICES) + ".\n")
    ev = evidence_table(a.benchmark_zip)
    R.append("## 3. v1 benchmark: memory share of limit reported in the preserved incidents' forecast evidence (integer percent), by 2-hour bin\n")
    piv = ev.pivot_table(index="hour", columns="service", values="share_pct", aggfunc="median")
    piv["incidents"] = ev.groupby("hour").size()
    R.append(piv.reset_index().to_markdown(index=False))
    R.append("\nFor scale: training medians in percent of the 256 MiB limit are about " + ", ".join(f"{s} {tr[s].median() / 268.435456 * 100:.0f}%" for s in SERVICES) + ".")
    Path(a.out).write_text("\n".join(R) + "\n", encoding="utf-8")
    print("\n".join(R))


if __name__ == "__main__":
    main()
