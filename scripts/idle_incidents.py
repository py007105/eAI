"""Read-only: list the incidents the brain opened while no challenge was running (before R4) and write docs/results/idle_incidents_pre_R4.md.

    python scripts/idle_incidents.py [--before <epoch s>] [--out docs/results/idle_incidents_pre_R4.md]

Uses GET /incidents (brain) and GET /scorecard (evaluator) only; changes nothing. An incident counts as idle when it opened before --before
(default: now) and the evaluator's scorecard holds no run, i.e. no challenge had been started since the launcher's reset.
"""
import argparse
import time
from pathlib import Path

import httpx

EAI, EV = "http://localhost:8000", "http://localhost:8200"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--before", type=float, default=time.time())
    ap.add_argument("--out", default="docs/results/idle_incidents_pre_R4.md")
    a = ap.parse_args()
    runs = httpx.get(f"{EV}/scorecard", timeout=10).json()["runs"]
    if runs:
        raise SystemExit(f"scorecard holds {runs} run(s): incidents can no longer be told apart from challenge incidents by this script")
    incs = [i for i in httpx.get(f"{EAI}/incidents", timeout=10).json() if i["opened_t"] < a.before]
    ts = lambda x: time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(x))
    L = ["# Incidents opened while no challenge was running (before R4; script output)", "",
         f"Read at {ts(time.time())} IST from the brain's `/incidents`; the evaluator's scorecard held {runs} runs, so no challenge had been started since the "
         "launcher's scorecard reset. These are incidents the brain opened on the idle stack (load generator running, no fault injected by the evaluator). "
         "Their cause is **unverified**: they are not fault detections, and they enter no evaluated count. They were left in place (no brain restart, no history deletion).", "",
         "| incident | opened (IST) | services flagged | likely cause | abstained | status | actions proposed or executed |", "|---|---|---|---|---|---|---|"]
    for i in incs:
        L.append(f"| {i['id']} | {ts(i['opened_t'])} | {', '.join(i.get('services') or [])} | {i['likely_cause']} | {i['abstained']} | {i['status']} | {len(i['actions'])} |")
    L += ["", f"Total: {len(incs)} incidents, {sum(len(i['actions']) for i in incs)} actions.", "",
          "**Telling them apart from a challenge during R4.** The dashboard's report, timeline and evidence panels show the most recent incident; they do not show "
          "its id or clock time, and the timeline is relative (+0.8 s ...). Until a challenge opens a new incident, the panels show the last idle incident above. "
          "To check by id and opening time (read-only), in window B: "
          "`(Invoke-RestMethod http://localhost:8000/incidents) | Select-Object id, @{n='opened';e={[DateTimeOffset]::FromUnixTimeSeconds([int64]$_.opened_t).LocalDateTime}}, status, likely_cause`. "
          "An incident opened before you ran `demo_challenge.py start` is not from that challenge. The evaluator's own count, printed by "
          "`demo_challenge.py reveal <RUN_ID>` (`incidents_opened`), includes only incidents opened from one second before that run's injection onward; "
          "an idle incident can still open during a challenge, and the evaluator counts it if it falls in that window."]
    Path(a.out).write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
