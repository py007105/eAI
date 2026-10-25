"""Live forecast check (docs/FORECAST_CHECK.md). Two modes:

    python tools/forecast_check.py collect --out results/forecast-check/raw [--seeds 3000 3001 3002 3003 3004] [--only memory_leak disk_fill ...]
    python tools/forecast_check.py analyze --raw results/forecast-check/raw --out docs/results/forecast_check.md [--fixture]

`collect` drives evaluator runs (the brain must already be running in WATCH-ONLY mode) and stores, per run, the evaluator's truth and score, the brain's /incidents
and /audit, and the Prometheus series of the target's memory, memory limit, scratch disk and start time. `analyze` reads only those files.
Criteria and definitions are fixed in docs/FORECAST_CHECK.md before any run. Seeds must be >= 3000 (non-benchmark).
"""
import argparse
import json
import random
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from harness_auth import check_started, evaluator_headers  # noqa: E402

SCENARIOS = ["memory_leak", "disk_fill", "traffic_surge", "good_deploy"]
GRADUAL = ["memory_leak", "disk_fill"]
HEALTHY = ["traffic_surge", "good_deploy"]
# v3 (2026-10-21): runs observe the full window (no early end) so the limit is really reached in watch-only mode; disk_fill uses
# the gradual variant (2-4 MB per 2 s, about 150-300 s to the 300 MB threshold). The default 30 s burst reaches the threshold in
# under 30 s, faster than any trend forecast can speak (it needs 30 s of steady growth): see docs/FORECAST_CHECK.md, v3.
TIMEOUT = {"memory_leak": 150, "disk_fill": 330}
RUN_OPTIONS = {"memory_leak": {"observe_full": True}, "disk_fill": {"observe_full": True, "variant": "gradual"}}
SCRATCH_LIMIT_BYTES = 300 * 1024 * 1024        # mirrors engine.config.SCRATCH_LIMIT_BYTES (SCRATCH_LIMIT_MB default 300)
MEM_LIMIT_FRACTION = 0.95
MIN_LEAD_S, MIN_WARNED = 30.0, 4              # pass criteria from FORECAST_CHECK.md: median lead >= 30 s; warned in >= 4 of 5 runs
EV, EAI, PROM = "http://localhost:8200", "http://localhost:8000", "http://localhost:9090"


# ----------------------------------------------------------------------------------------------------- analysis (pure)
def first_crossing(series, threshold, after):
    for t, v in series:
        if t >= after and v is not None and v >= threshold:
            return t
    return None


def t_limit(run):
    """First of: memory >= 95% of its limit, scratch disk >= limit, a restart of the target after injection, or the target no longer
    scraped (up == 0: the process died, e.g. OOM-killed; containers are not restarted automatically)."""
    sc, t0 = run["scenario"], run["truth"]["t_inject"]
    p = run["prom"]
    cands = []
    if sc == "memory_leak":
        lim = max((v for _, v in p.get("mem_limit", []) if v), default=None)
        if lim:
            cands.append(first_crossing(p.get("mem", []), MEM_LIMIT_FRACTION * lim, t0))
    if sc == "disk_fill":
        cands.append(first_crossing(p.get("scratch", []), SCRATCH_LIMIT_BYTES, t0))
    st = [v for _, v in p.get("start", []) if v is not None]
    if st:
        base = st[0]
        for t, v in p["start"]:
            if t >= t0 and v is not None and v != base:
                cands.append(t)
                break
    for t, v in p.get("up", []):
        if t >= t0 and v is not None and v == 0:
            cands.append(t)
            break
    cands = [c for c in cands if c is not None]
    return min(cands) if cands else None


def warnings_of(incidents):
    """Every forecast warning, as (time, service, forecast). v3: the engine attaches a timestamped warning ("t") to whatever incident is
    active, or opens a predicted incident; older predicted incidents without "t" count at their opening time."""
    out = []
    for i in incidents:
        for f in i.get("forecasts") or []:
            if "t" in f:
                out.append((f["t"], f.get("service") or (i.get("services") or [None])[0], f))
            elif i.get("kind") == "predicted":
                out.append((i["opened_t"], (i.get("services") or [None])[0], f))
    return sorted(out, key=lambda w: w[0])


def analyse_run(run):
    t0, t_end, target = run["truth"]["t_inject"], run["score"].get("t_end", run["truth"]["t_inject"] + 1e9), run["truth"]["target"]
    inc = [i for i in run["incidents"] if t0 - 1 <= i["opened_t"] <= t_end]
    predicted = sorted((i for i in inc if i.get("kind") == "predicted"), key=lambda i: i["opened_t"])
    warns = warnings_of(inc)
    warn = warns[0] if warns else None                      # (time, service, forecast)
    ev_forecast = [e for i in inc if i.get("kind") != "predicted" for e in (i.get("evidence") or []) if e.get("tool") == "forecast"]
    tl = t_limit(run) if run["scenario"] in GRADUAL else None
    fc = warn[2] if warn else None
    lead = (tl - warn[0]) if (warn and tl is not None) else None
    executed = sum(1 for i in inc for a in (i.get("actions") or []) if a.get("executed")) + sum(1 for a in run.get("audit", []) if a.get("t", 0) >= t0)
    inside = None
    if fc and lead is not None:
        inside = bool(fc["eta_earliest_s"] <= lead <= fc["eta_latest_s"])
    return {"scenario": run["scenario"], "seed": run["seed"], "target": target, "incidents": len(inc), "predicted incidents": len(predicted),
            "warnings": len(warns), "warned": warn is not None, "warning service": warn[1] if warn else None,
            "wrong service": bool(warn and warn[1] != target),
            "t_warn_after_inject_s": round(warn[0] - t0, 1) if warn else None,
            "t_limit_after_inject_s": round(tl - t0, 1) if tl is not None else None, "limit_reached": tl is not None,
            "lead_s": round(lead, 1) if lead is not None else None, "stated_window_s": (round(fc["eta_earliest_s"]), round(fc["eta_latest_s"])) if fc else None,
            "actual_inside_window": inside, "forecast_evidence_on_reactive": len(ev_forecast), "executed_actions": executed}


def evaluate(rows):
    crit = []
    for sc in GRADUAL:
        r = [x for x in rows if x["scenario"] == sc]
        warned = [x for x in r if x["warned"] and x["lead_s"] is not None and x["lead_s"] > 0]
        leads = sorted(x["lead_s"] for x in warned)
        med = (leads[len(leads) // 2] if len(leads) % 2 else (leads[len(leads) // 2 - 1] + leads[len(leads) // 2]) / 2) if leads else None
        crit.append((f"{sc}: warning issued before the limit in at least {MIN_WARNED} of 5 runs", len(warned) >= MIN_WARNED, f"{len(warned)} of {len(r)} runs"))
        crit.append((f"{sc}: median lead time at least {MIN_LEAD_S:.0f} s", med is not None and med >= MIN_LEAD_S,
                     f"median {med} s over {len(leads)} warned runs; leads {leads}"))
        crit.append((f"{sc}: warnings on the wrong service", not any(x["wrong service"] for x in r), f"{sum(x['wrong service'] for x in r)} in {len(r)} runs"))
    for sc in HEALTHY:
        r = [x for x in rows if x["scenario"] == sc]
        n = sum(x["warnings"] for x in r)
        crit.append((f"{sc}: warnings (any forecast warning)", n == 0, f"{n} warnings in {len(r)} healthy runs"))
    allr = rows
    crit.append(("watch-only: executed actions in every run", all(x["executed_actions"] == 0 for x in allr),
                 f"{sum(x['executed_actions'] for x in allr)} executed actions in {len(allr)} runs"))
    crit.append(("watch-only: an incident opened in each leak/disk run", all(x["incidents"] > 0 for x in allr if x["scenario"] in GRADUAL),
                 f"{sum(1 for x in allr if x['scenario'] in GRADUAL and x['incidents'] > 0)} of {sum(1 for x in allr if x['scenario'] in GRADUAL)} runs"))
    return crit


def render(rows, crit, fixture=False):
    import pandas as pd
    R = ["# Forecast check (live, watch-only)" + (" (FIXTURE)" if fixture else ""), ""]
    if fixture:
        R.append("> **FIXTURE DATA, NOT RESULTS.**\n")
    R.append("Design, definitions and pass criteria: `docs/FORECAST_CHECK.md`, fixed before the runs. Brain in watch-only mode, non-benchmark seeds, template LLM path not involved. "
             "Counts over the runs actually made; with 5 runs per scenario no rate or interval is claimed.\n")
    R.append("## Criteria\n\n| criterion | result | detail |\n|---|---|---|")
    R += [f"| {c} | {'PASS' if ok else 'FAIL'} | {d} |" for c, ok, d in crit]
    R.append("\n## Per run\n")
    R.append(pd.DataFrame(rows).sort_values(["scenario", "seed"]).to_markdown(index=False))
    R.append("\n`lead_s` = limit time (95% memory, disk threshold, restart or process death) minus first warning time; empty when no warning or the limit was never reached before the run ended (censored). "
             "`forecast_evidence_on_reactive` counts forecast evidence items attached to reactive incidents; they are not warnings. "
             "A warning is a timestamped forecast the engine attached to an incident, or a predicted incident (v3, docs/FORECAST_CHECK.md).")
    return "\n".join(R) + "\n"


# ----------------------------------------------------------------------------------------------------- collection (live)
def prom_range(q, start, end):
    import httpx
    r = httpx.get(f"{PROM}/api/v1/query_range", params={"query": q, "start": start, "end": end, "step": 2}, timeout=15).json()["data"]["result"]
    return [(float(t), float(v)) for t, v in r[0]["values"]] if r else []


def collect(a):
    import httpx
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    st = httpx.get(f"{EAI}/status", timeout=5).json()
    assert st.get("mode") == "watch-only" and st.get("brain") == "eternalai", f"brain must be eternalai in watch-only mode, got {st.get('brain')} / {st.get('mode')}"
    jobs = [(sc, s) for sc in (a.only or SCENARIOS) for s in a.seeds]
    assert all(s >= 3000 for _, s in jobs), "forecast-check seeds must be >= 3000"
    random.Random(2026).shuffle(jobs)
    for sc, seed in jobs:
        f = out / f"{sc}_{seed}.json"
        if f.exists():
            continue
        r = check_started(httpx.post(f"{EV}/runs", headers=evaluator_headers(), json={"scenario": sc, "seed": seed, "timeout_s": TIMEOUT.get(sc, 90), "healthy_s": 60, **RUN_OPTIONS.get(sc, {})}, timeout=20))
        if r.status_code != 200:
            print(f"{sc} {seed}: could not start ({r.status_code})", flush=True)
            continue
        rid = r.json()["run_id"]
        while httpx.get(f"{EV}/runs/{rid}/status", timeout=10).json()["state"] == "running":
            time.sleep(3)
        rev = httpx.get(f"{EV}/runs/{rid}/reveal", timeout=10)
        if rev.status_code != 200:
            print(f"{sc} {seed}: run failed: {httpx.get(f'{EV}/runs/{rid}/status', timeout=10).json().get('error')}", flush=True)
            continue
        truth, score = rev.json()["truth"], rev.json()["score"]
        t0, t_end, tgt = truth["t_inject"], score["t_end"], truth["target"]
        prom = {"mem": prom_range(f'app_memory_bytes{{service="{tgt}"}}', t0 - 30, t_end + 5),
                "mem_limit": prom_range(f'app_memory_limit_bytes{{service="{tgt}"}}', t0 - 30, t_end + 5),
                "scratch": prom_range(f'app_scratch_disk_bytes{{service="{tgt}"}}', t0 - 30, t_end + 5),
                "start": prom_range(f'app_start_time_seconds{{service="{tgt}"}}', t0 - 30, t_end + 5),
                "up": prom_range(f'up{{job="app",instance_name="{tgt}"}}', t0 - 30, t_end + 5)}
        row = {"scenario": sc, "seed": seed, "truth": truth, "score": score, "incidents": httpx.get(f"{EAI}/incidents", timeout=10).json(),
               "audit": httpx.get(f"{EAI}/audit", timeout=10).json(), "prom": prom, "finished_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
        f.write_text(json.dumps(row))
        print(f"{sc} seed {seed}: saved ({len(row['incidents'])} incidents in brain)", flush=True)


def analyze(a):
    runs = [json.loads(p.read_text()) for p in sorted(Path(a.raw).glob("*.json"))]
    # only incidents of this run (the brain keeps history across runs); analyse_run filters by the run's window
    rows = [analyse_run(r) for r in runs]
    text = render(rows, evaluate(rows), a.fixture)
    if a.fixture and Path(a.out).resolve().as_posix().endswith("docs/results/forecast_check.md"):
        sys.exit("refusing to write fixture output to the real results path")
    Path(a.out).write_text(text, encoding="utf-8")
    print(text)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("collect")
    c.add_argument("--out", required=True)
    c.add_argument("--seeds", type=int, nargs="+", default=[3000, 3001, 3002, 3003, 3004])
    c.add_argument("--only", nargs="*", choices=SCENARIOS)
    z = sub.add_parser("analyze")
    z.add_argument("--raw", required=True)
    z.add_argument("--out", required=True)
    z.add_argument("--fixture", action="store_true")
    a = ap.parse_args()
    collect(a) if a.cmd == "collect" else analyze(a)


if __name__ == "__main__":
    main()
