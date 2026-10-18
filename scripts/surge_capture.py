"""Read-only capture for the surge diagnosis (docs/postmortems/surge-false-alarm-diagnosis.md, hypotheses H1-H3, H6).

    python scripts/surge_capture.py collect --out results/surge-capture/raw [--seeds 3600 3601 ...]
    python scripts/surge_capture.py analyze --raw results/surge-capture/raw --out docs/results/surge_capture.md [--fixture]

`collect` runs `traffic_surge` through the evaluator on NON-benchmark seeds (3600-3699) with the brain in WATCH-ONLY mode (it opens and diagnoses incidents but never
acts), and stores per run: the surge level (from the evaluator's truth), the Prometheus memory / memory limit / request-rate / start-time series of every service, container uptime context,
and the brain's incidents (with the v2 `diagnosis` record when the brain is a v2 build). `analyze` compares the memory peak of each service during the surge with the learned
healthy limits of the frozen detector, by surge level, and lists the incidents the brain opened. It changes and trains nothing. Which seeds give which level is decided by the
evaluator's rng and is planned with scripts/plan_v2_seeds.py (`sim_surge_level`).
"""
import argparse
import json
import sys
import time
from pathlib import Path

SERVICES = ["web", "orders", "payments", "inventory"]
EV, EAI, PROM = "http://localhost:8200", "http://localhost:8000", "http://localhost:9090"


def prom_range(q, start, end):
    import httpx
    r = httpx.get(f"{PROM}/api/v1/query_range", params={"query": q, "start": start, "end": end, "step": 2}, timeout=15).json()["data"]["result"]
    return [(float(t), float(v)) for t, v in r[0]["values"]] if r else []


def collect(a):
    import httpx
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    st = httpx.get(f"{EAI}/status", timeout=5).json()
    assert st.get("mode") == "watch-only", f"the brain must be in watch-only mode, got {st.get('mode')}"
    assert all(3600 <= s <= 3699 for s in a.seeds), "capture seeds must lie in 3600-3699"
    for seed in a.seeds:
        f = out / f"traffic_surge_{seed}.json"
        if f.exists():
            continue
        r = httpx.post(f"{EV}/runs", json={"scenario": "traffic_surge", "seed": seed, "timeout_s": 90, "healthy_s": 60}, timeout=20)
        if r.status_code != 200:
            print(f"{seed}: could not start ({r.status_code})", flush=True)
            continue
        rid = r.json()["run_id"]
        while httpx.get(f"{EV}/runs/{rid}/status", timeout=10).json()["state"] == "running":
            time.sleep(3)
        rev = httpx.get(f"{EV}/runs/{rid}/reveal", timeout=10)
        if rev.status_code != 200:
            print(f"{seed}: run failed", flush=True)
            continue
        truth, score = rev.json()["truth"], rev.json()["score"]
        t0, t_end = truth["t_inject"], score["t_end"]
        prom = {}
        for s in SERVICES:
            prom[s] = {"mem": prom_range(f'app_memory_bytes{{service="{s}"}}', t0 - 60, t_end + 5),
                       "mem_limit": prom_range(f'app_memory_limit_bytes{{service="{s}"}}', t0 - 60, t_end + 5),
                       "rps": prom_range(f'sum(rate(http_requests_total{{service="{s}"}}[10s]))', t0 - 60, t_end + 5),
                       "start": prom_range(f'app_start_time_seconds{{service="{s}"}}', t0 - 60, t_end + 5)}
        row = {"seed": seed, "truth": truth, "score": score, "incidents": httpx.get(f"{EAI}/incidents", timeout=10).json(), "prom": prom,
               "finished_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
        tmp = f.with_name(f.name + ".tmp")        # atomic: a kill leaves no half-written run
        tmp.write_text(json.dumps(row))
        tmp.replace(f)
        print(f"surge seed {seed} level {truth['params'].get('extra_rps_per_thread')}: saved", flush=True)


def analyse_run(run, limits):
    """limits: {service: learned mem_share hi limit}. Returns per-service memory facts during the surge window."""
    t0, t_end = run["truth"]["t_inject"], run["score"]["t_end"]
    inc = [i for i in run["incidents"] if t0 - 1 <= i["opened_t"] <= t_end]
    row = {"seed": run["seed"], "surge level": run["truth"]["params"]["extra_rps_per_thread"], "incidents opened in run window": len(inc),
           "diagnosed as": sorted({i.get("likely_cause") for i in inc}) or "-"}
    for s in SERVICES:
        p = run["prom"][s]
        lim = max((v for _, v in p["mem_limit"] if v), default=None)
        during = [v for t, v in p["mem"] if t0 + 5 <= t <= t_end]
        before = [v for t, v in p["mem"] if t0 - 40 <= t < t0 - 5]
        if lim and during and before:
            row[f"{s} MB before"] = round(sorted(before)[len(before) // 2] / 1e6, 1)
            row[f"{s} MB peak in surge"] = round(max(during) / 1e6, 1)
            row[f"{s} peak share of limit"] = round(max(during) / lim, 4)
            row[f"{s} exceeds learned limit"] = bool(limits.get(s) is not None and max(during) / lim > limits[s])
    return row


def render(rows, limits, fixture=False):
    import pandas as pd
    R = ["# Surge capture (read-only, watch-only brain, non-benchmark seeds)" + (" (FIXTURE)" if fixture else ""), ""]
    if fixture:
        R.append("> **FIXTURE DATA, NOT RESULTS.**\n")
    R.append("Memory of each service during a traffic surge compared with the learned healthy `mem_share` limit of the frozen detector "
             f"(limits used: {limits}). Counts over the runs actually made; nothing was trained or changed.\n")
    df = pd.DataFrame(rows).sort_values(["surge level", "seed"])
    R.append(df.to_markdown(index=False))
    R.append("\n## Summary by surge level\n")
    summ = []
    for lv, g in df.groupby("surge level"):
        row = {"surge level": lv, "runs": len(g), "runs with an incident": int((g["incidents opened in run window"] > 0).sum())}
        for s in SERVICES:
            c = f"{s} exceeds learned limit"
            if c in g:
                row[f"{s}: runs exceeding limit"] = int(g[c].sum())
        summ.append(row)
    R.append(pd.DataFrame(summ).to_markdown(index=False))
    return "\n".join(R) + "\n"


def learned_limits():
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from eternalai import artifacts
    det, _ = artifacts.load("detectors")
    return {s: float(d.limits["mem_share"][1]) for s, d in det.items() if "mem_share" in d.limits}


def analyze(a):
    runs = [json.loads(p.read_text()) for p in sorted(Path(a.raw).glob("*.json"))]
    limits = json.loads(a.limits) if a.limits else learned_limits()
    text = render([analyse_run(r, limits) for r in runs], limits, a.fixture)
    if a.fixture and Path(a.out).resolve().as_posix().endswith("docs/results/surge_capture.md"):
        sys.exit("refusing to write fixture output to the real results path")
    Path(a.out).write_text(text, encoding="utf-8")
    print(text)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("collect")
    c.add_argument("--out", required=True)
    c.add_argument("--seeds", type=int, nargs="+", required=True)
    z = sub.add_parser("analyze")
    z.add_argument("--raw", required=True)
    z.add_argument("--out", required=True)
    z.add_argument("--limits", help='JSON {"inventory": 0.2603, ...}; default: read from the frozen detectors artifact')
    z.add_argument("--fixture", action="store_true")
    a = ap.parse_args()
    collect(a) if a.cmd == "collect" else analyze(a)


if __name__ == "__main__":
    main()
