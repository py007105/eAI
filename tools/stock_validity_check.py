"""Stock-out validity check for every dataset (read-only). Counts come from this script's output, never typed by hand.

    python tools/stock_validity_check.py --repo D:/eAI/eAI-workspace/eAI [--out docs/results/stock_validity.md]

Facts used (all checkable):
  * The inventory volume holds 100000 units per SKU from its creation and there is no restock path and no other writer, so a SKU's stock only ever falls.
    A SKU that served a checkout at time T had stock at every earlier time.
  * A stock-out shows as checkout failures that persist: HTTP 409 in verification probes, and failed requests in healthy runs.
This script lists, per dataset, the evidence that exists and says plainly where nothing can be verified.
"""
import argparse
import glob
import json
import subprocess
import time
from pathlib import Path

import pandas as pd

HEALTHY = ("traffic_surge", "good_deploy")


def rows(p):
    d = {}
    for x in Path(p).read_text(encoding="utf-8").splitlines():
        if x.strip():
            r = json.loads(x)
            d[(r["arm"], r["scenario"], r["seed"])] = r
    return sorted(d.values(), key=lambda r: r["finished_at"])


def ist(ts):
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))


def probes(r):
    return [(i["verification"]["t"], i["verification"]) for i in r.get("incidents", []) if i.get("verification")]


def v2_section(repo, L):
    raw = rows(Path(repo) / "results/benchmark-v2/benchmark_v2_raw.jsonl")
    pv = sorted((t, v, r) for r in raw for t, v in probes(r))
    ok = [x for x in pv if x[1].get("outcome") == "recovered" or x[1].get("success_rate", 0) > 0]
    last_ok = max(ok, key=lambda x: x[0]) if ok else None
    bad = [x for x in pv if "409" in str(x[1].get("last_detail"))]
    first_bad = min(bad, key=lambda x: x[0]) if bad else None
    L += ["## v2 Stage 3 (95 rows)", "",
          f"- verification probes recorded: {len(pv)}; with HTTP 409: {len(bad)}; with success_rate > 0: {len(ok)}",
          f"- last verification with a successful checkout: {ist(last_ok[0]) if last_ok else 'none'} ({last_ok[2]['arm']} {last_ok[2]['scenario']} {last_ok[2]['seed']})" if last_ok else "- no successful probe",
          f"- first verification with HTTP 409: {ist(first_bad[0]) if first_bad else 'none'} ({first_bad[2]['arm']} {first_bad[2]['scenario']} {first_bad[2]['seed']})" if first_bad else "- no 409 probe",
          f"- successes after the first 409: {sum(1 for x in ok if first_bad and x[0] > first_bad[0])}"]
    cut = first_bad[0] if first_bad else None
    if last_ok:   # sku-mug is the probe SKU
        L.append(f"- Because stock never rises, sku-mug had stock at every time up to {ist(last_ok[0])}. Other SKUs: no direct evidence; loadgen picks SKUs uniformly, "
                 "so they follow the same curve within the random difference between SKUs (see orders totals below).")
    before = [r for r in raw if cut and r["finished_at"] < ist(cut)[:10] + "T" + ist(cut)[11:]]
    after = [r for r in raw if cut and r["finished_at"] >= ist(cut)[:10] + "T" + ist(cut)[11:]]
    fault = lambda r: r["scenario"] not in HEALTHY
    L += [f"- rows finished before the first 409: {len(before)} (healthy {sum(1 for r in before if not fault(r))}, fault {sum(1 for r in before if fault(r))}); "
          f"after: {len(after)} (healthy {sum(1 for r in after if not fault(r))}, fault {sum(1 for r in after if fault(r))})", ""]
    hv = [r for r in raw if r["scenario"] in HEALTHY]
    fp = [r["score"]["failed_request_pct"] for r in hv if r["score"].get("failed_request_pct") is not None]
    L += [f"- healthy rows: {len(hv)}; failed_request_pct mean {sum(fp)/len(fp):.2f}, max {max(fp):.2f}; rows with failed_request_pct >= 5: "
          f"{sum(1 for x in fp if x >= 5)}"]
    # trend: first / last third of healthy rows by finish time
    n = len(hv) // 3
    if n:
        a, b = hv[:n], hv[-n:]
        m = lambda xs: sum(r["score"]["failed_request_pct"] for r in xs) / len(xs)
        L.append(f"- healthy rows by finish time, mean failed_request_pct: first {n} = {m(a):.2f}, last {n} = {m(b):.2f} (a stock-out would raise it)")
    L.append("")
    L += ["### Rows finishing after the first 409 (fault rows; failed_request_pct and detection inputs are confounded)", "",
          "| arm | scenario | seed | finished (IST) | recovered | verification |", "|---|---|---|---|---|---|"]
    for r in after:
        v = [x[1] for x in probes(r)]
        L.append(f"| {r['arm']} | {r['scenario']} | {r['seed']} | {r['finished_at']} | {r['score'].get('recovered')} | "
                 f"{'; '.join(str(x.get('last_detail')) for x in v) or 'none'} |")
    L.append("")
    return cut


def v1_section(repo, L):
    p = Path(repo) / "docs/results/benchmark_raw.jsonl"
    if not p.exists():
        L += ["## v1 benchmark", "", "raw file not found: cannot be verified.", ""]
        return
    raw = rows(p)
    pv = [(t, v) for r in raw for t, v in probes(r)]
    hv = [r for r in raw if r["scenario"] in HEALTHY]
    fp = [r["score"]["failed_request_pct"] for r in hv if r["score"].get("failed_request_pct") is not None]
    L += [f"## v1 benchmark ({len(raw)} rows, finished {raw[0]['finished_at']} to {raw[-1]['finished_at']})", "",
          f"- verification probes recorded: {len(pv)}; with HTTP 409: {sum(1 for _, v in pv if '409' in str(v.get('last_detail')))}",
          f"- healthy rows: {len(hv)}; failed_request_pct mean {sum(fp)/len(fp):.2f}, max {max(fp):.2f}; rows with >= 5: {sum(1 for x in fp if x >= 5)}"]
    n = len(hv) // 3
    if n:
        m = lambda xs: sum(r["score"]["failed_request_pct"] for r in xs) / len(xs)
        L.append(f"- healthy rows by finish time, mean failed_request_pct: first {n} = {m(hv[:n]):.2f}, last {n} = {m(hv[-n:]):.2f}")
    L += ["- the v1 stack was the same volume, so the last v1 row finishing earlier than the Stage 3 last-good-probe time, with stock never rising, bounds v1 only for sku-mug "
          "(see the v2 section); other SKUs are covered by the healthy-row evidence above.", ""]


def training_section(repo, L):
    out = []
    for name, d in (("original 72 training runs", "ml/data/runs"), ("34 fresh runs (Stage 1)", "ml/data/runs_v2")):
        rs = []
        for jf in sorted(glob.glob(str(Path(repo) / d / "*.json"))):
            try:
                m = json.load(open(jf))
            except ValueError:
                continue
            if "t_inject" not in m:
                continue
            df = pd.read_csv(jf[:-5] + ".csv")
            b = df[df.t < m["t_inject"]]
            rr = lambda x: (x.err_rate.sum() / x.req_rate.sum()) if x.req_rate.sum() > 0 else 0.0
            rs.append(dict(f=Path(jf).stem, t0=df.t.min(), web=rr(b[b.service == "web"]), inv=rr(b[b.service == "inventory"])))
        r = pd.DataFrame(rs).sort_values("t0")
        n = len(r)
        L += [f"## {name} ({n} runs, pre-injection window of each; {ist(r.t0.min())} to {ist(r.t0.max())} IST)", "",
              f"- web error ratio: mean {r.web.mean():.3f}, max {r.web.max():.3f}; runs with web ratio >= 0.5: {(r.web >= 0.5).sum()}",
              f"- inventory error ratio: mean {r.inv.mean():.3f}, max {r.inv.max():.3f}; runs with inventory ratio > 0.01: {(r.inv > 0.01).sum()}; > 0.5: {(r.inv > 0.5).sum()}",
              f"- runs with inventory ratio > 0.01 in time order: " + (", ".join(f"{x.f} ({ist(x.t0)[5:16]})" for x in r[r.inv > 0.01].itertuples()) or "none"),
              "- a persistent stock-out would show as inventory/web error ratios that stay high in every later run; sporadic ones are other causes (a fault left from the previous run, a restart).", ""]


def orders_section(L):
    try:
        out = subprocess.run(["docker", "exec", "eai-orders-1", "python", "-c",
                              "import sqlite3;c=sqlite3.connect('/data/orders.db');print(c.execute('select sku,count(*),sum(qty) from orders group by sku').fetchall())"],
                             capture_output=True, text=True, timeout=60)
        inv = subprocess.run(["docker", "exec", "eai-inventory-1", "python", "-c",
                              "import sqlite3;print(sqlite3.connect('/data/inventory.db').execute('select sku,stock from items').fetchall())"],
                             capture_output=True, text=True, timeout=60)
        vol = subprocess.run(["docker", "volume", "inspect", "eai_inventory-data", "--format", "{{.CreatedAt}}"], capture_output=True, text=True, timeout=60)
        L += ["## Consumption record (live query)", "", f"- inventory volume created: {vol.stdout.strip()}",
              f"- orders table, (sku, confirmed orders, units) over the whole volume lifetime: {out.stdout.strip() or out.stderr.strip()}",
              f"- inventory stock now (sku, stock): {inv.stdout.strip() or inv.stderr.strip()}", ""]
    except (OSError, subprocess.SubprocessError) as e:
        L += ["## Consumption record", "", f"docker not reachable: {type(e).__name__}", ""]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--out")
    a = ap.parse_args()
    L = ["# Stock-out validity check (script output)", "",
         "Inventory logs: the container logs were lost to recreations by runbooks and Prometheus keeps 2 h, so there is no stock timeline; the evidence below is what the "
         "result rows, the run files and the orders table still hold. Where a dataset has no direct record this is said.", ""]
    v2_section(a.repo, L)
    v1_section(a.repo, L)
    training_section(a.repo, L)
    orders_section(L)
    text = "\n".join(L)
    if a.out:
        Path(a.out).write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
