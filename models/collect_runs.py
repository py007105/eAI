"""Generate labelled training data from the live stack, using the independent evaluator.

    python models/collect_runs.py --reps 10 [--seed0 1000] [--out data/runs]

For each (scenario, rep) it asks the evaluator to inject a fault with a TRAINING seed, waits
for the run to finish, reveals the truth through the evaluator API (offline training use only),
and saves the raw per-service signals from Prometheus around the injection. Held-out
evaluation uses different seeds (< 1000), so train and test runs never share a seed.
EternalAI is not running during collection, so these are no-action runs.
"""
import argparse
import json
import random
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from eternalai import config  # noqa: E402
from eternalai.collector import Prom  # noqa: E402

EV = "http://localhost:8200"
SCENARIOS = ["crash", "latency", "error_spike", "memory_leak", "disk_fill", "bad_deploy",
             "cpu_burn", "traffic_surge", "good_deploy"]
TIMEOUT = {"memory_leak": 100, "disk_fill": 80}
DEFAULT_TIMEOUT = 45


def scenario_order(rep: int, scenarios: list[str]) -> list[tuple[int, str]]:
    """(index, scenario) pairs in a per-repetition shuffled order, so run order cannot predict the label."""
    order = list(enumerate(scenarios))
    random.Random(rep).shuffle(order)
    return order


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=10)
    ap.add_argument("--seed0", type=int, default=1000)
    ap.add_argument("--out", default="data/runs")
    ap.add_argument("--scenarios", nargs="*", default=SCENARIOS)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    prom = Prom()
    n = 0
    for rep in range(a.reps):
        for si, scen in scenario_order(rep, a.scenarios):
            seed = a.seed0 + rep * 100 + si
            tag = out / f"{scen}_{seed}"
            if (tag.with_suffix(".json")).exists():
                continue
            r = httpx.post(f"{EV}/runs", json={"scenario": scen, "seed": seed,
                                               "timeout_s": TIMEOUT.get(scen, DEFAULT_TIMEOUT), "healthy_s": 60}, timeout=20)
            r.raise_for_status()
            rid = r.json()["run_id"]
            while httpx.get(f"{EV}/runs/{rid}/status", timeout=10).json()["state"] == "running":
                time.sleep(5)
            rev = httpx.get(f"{EV}/runs/{rid}/reveal", timeout=10)
            if rev.status_code != 200:
                err = httpx.get(f"{EV}/runs/{rid}/status", timeout=10).json().get("error", "unknown")
                print(f"{scen} seed {seed}: run failed ({err}), skipping; rerun to retry this seed", flush=True)
                continue
            truth = rev.json()["truth"]
            t0 = truth["t_inject"]
            # leave out the restore that follows the run: use the evaluator's own end of observation when it
            # reports one (current evaluator), else the old heuristic (evaluator images before 2026-10-17)
            end = rev.json()["score"].get("t_end") or (time.time() - 12)
            span_end = min(t0 + 100, end)
            frames = {}
            for s in config.SERVICES:
                df = prom.signals(s, seconds=int(span_end - (t0 - 240)), end=span_end)
                frames[s] = df
            import pandas as pd
            pd.concat(frames, names=["service", "t"]).to_csv(tag.with_suffix(".csv"))
            tag.with_suffix(".json").write_text(json.dumps(truth))
            n += 1
            print(f"saved {tag.name} target={truth['target']} ({n} new)", flush=True)


if __name__ == "__main__":
    main()
