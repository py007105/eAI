"""Passive recorder for the human-driven rehearsal R3 (tooling only; read-only: it sends GET requests and never starts, approves or rejects anything).

    python tools/r3_monitor.py --out results/rehearsals/R3_monitor.jsonl          # stop with Ctrl+C or by killing the process

Every 3 s it records free RAM and, when something changed, the brain's incident list (status, ranking, services, diagnosis), the pending approvals exactly as the
dashboard receives them, the anomalous services (what the service map colours), and the evaluator's scorecard count. `render_rehearsals.py` turns the log into
the R3 timings: first incident, approval seen, recovery, scorecard, minimum free RAM, and what was on screen in an unseen-fault case.
"""
import argparse
import json
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
import memguard  # noqa: E402

EAI, EV = "http://localhost:8000", "http://localhost:8200"


def get(url):
    try:
        return httpx.get(url, timeout=5).json()
    except (httpx.HTTPError, ValueError):
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    last = None
    with out.open("a", encoding="utf-8") as f:
        while True:
            t = time.time()
            inc, appr, svc, sc = get(f"{EAI}/incidents"), get(f"{EAI}/approvals"), get(f"{EAI}/services"), get(f"{EV}/scorecard")
            state = {
                "incidents": [{k: i.get(k) for k in ("id", "opened_t", "closed_t", "status", "kind", "likely_cause", "abstained", "confidence", "ranking", "services",
                                                     "actions", "verification", "diagnosis", "report_meta")} for i in (inc or [])],
                "approvals": appr, "anomalous": sorted(s for s, v in ((svc or {}).get("services") or {}).items() if v and v.get("anomalous")),
                "scorecard_runs": (sc or {}).get("runs"), "mode": (get(f"{EAI}/status") or {}).get("mode")}
            key = json.dumps(state, sort_keys=True, default=str)
            rec = {"t": t, "free_ram_gb": round(memguard.free_ram_gb(), 2)}
            if key != last:
                rec["state"], last = state, key
            f.write(json.dumps(rec, default=str) + "\n")
            f.flush()
            time.sleep(3)


if __name__ == "__main__":
    main()
