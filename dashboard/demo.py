"""Demo mode: start, follow and reveal evaluator runs from the dashboard server, so the presenter never needs a terminal on stage.

Same rules as tools/demo_challenge.py: a hidden pick from the six supported faults and the two healthy scenarios (never the unseen
fault), or the clearly labelled unseen-fault segment. The scenario is drawn here, on the server, with `secrets`; it is sent only to the
evaluator and never to the browser, so the page cannot show it before the reveal. Talks to the evaluator's existing API only
(POST /runs, GET /runs/{id}/status, GET /runs/{id}/reveal, GET /scorecard). Only runs started from this dashboard are tracked: the
evaluator has no endpoint that lists runs, so a run started from a terminal is not visible here.
"""
from __future__ import annotations

import os
import secrets
import threading
import time

import requests

POOL = ["crash", "latency", "error_spike", "memory_leak", "disk_fill", "bad_deploy", "traffic_surge", "good_deploy"]
UNSEEN = "cpu_burn"
HEALTHY = {"traffic_surge", "good_deploy"}


def evaluator_url() -> str:
    """EVALUATOR_URL if set; inside the compose network (backend reached as "eternalai") the evaluator service; otherwise localhost."""
    if os.getenv("EVALUATOR_URL"):
        return os.environ["EVALUATOR_URL"]
    return "http://evaluator:8200" if "eternalai:" in os.getenv("BACKEND_URL", "") else "http://localhost:8200"


class DemoRuns:
    def __init__(self, base: str | None = None, http=requests):
        self.base, self.http = base or evaluator_url(), http
        self.lock = threading.Lock()
        self.runs: list[dict] = []          # newest last: run_id, segment, started_t, baseline, state, phase, elapsed_s, reveal
        self.last_poll_error: str | None = None

    # ------------------------------------------------------------------ actions (called from callbacks)
    def current(self):
        with self.lock:
            return dict(self.runs[-1]) if self.runs else None

    def busy(self) -> bool:
        c = self.current()
        return bool(c and c["phase"] in ("starting", "running", "restoring"))

    def start(self, segment: str, mode: str | None, token: str | None = None) -> tuple[bool, str]:
        """segment: "hidden" or "unseen". `token`: the approval token typed on the page; the evaluator requires it to start
        a run (a run injects a real fault). It is sent as a header and never stored or shown. Returns (ok, message key or detail)."""
        token = (token or "").strip()
        if not token:
            return False, "demo_token_needed"
        if self.busy():
            return False, "demo_busy"
        if segment == "unseen" and mode != "ask-first":
            return False, "demo_unseen_needs_ask_first"
        scen = UNSEEN if segment == "unseen" else secrets.choice(POOL)
        try:
            baseline = self.http.get(f"{self.base}/scorecard", timeout=5).json().get("runs", 0)
            r = self.http.post(f"{self.base}/runs", json={"scenario": scen}, timeout=15, headers={"X-Approval-Token": token})
        except (requests.exceptions.InvalidHeader, UnicodeEncodeError):
            return False, "token_invalid"          # requests' own message would repeat the token
        except (requests.RequestException, ValueError) as e:
            return False, f"evaluator unreachable: {type(e).__name__}"
        if r.status_code in (403, 503):
            return False, "demo_token_refused"
        if r.status_code == 409:
            return False, "demo_conflict"
        if r.status_code != 200:
            return False, f"evaluator HTTP {r.status_code}"
        with self.lock:
            self.runs.append({"run_id": r.json()["run_id"], "segment": segment, "started_t": time.time(), "baseline": baseline,
                              "state": "running", "phase": "running", "elapsed_s": 0.0, "reveal": None})
        return True, "demo_started"

    def reveal(self) -> tuple[bool, str]:
        c = self.current()
        if not c:
            return False, "demo_nothing"
        if c["phase"] != "finished":
            return False, "demo_not_finished"
        try:
            r = self.http.get(f"{self.base}/runs/{c['run_id']}/reveal", timeout=10)
        except requests.RequestException as e:
            return False, f"evaluator unreachable: {type(e).__name__}"
        if r.status_code != 200:
            return False, f"evaluator HTTP {r.status_code}"
        with self.lock:
            self.runs[-1]["reveal"] = r.json()
        return True, "demo_revealed"

    # ------------------------------------------------------------------ polling (background thread)
    def poll(self):
        """Update the current run's state. 'restoring' = the evaluator still says running but the run is already scored (the scorecard
        count passed the baseline): it is restoring the stack, and a new run would get HTTP 409 until it finishes."""
        c = self.current()
        if not c or c["phase"] in ("finished", "failed"):
            return
        try:
            st = self.http.get(f"{self.base}/runs/{c['run_id']}/status", timeout=(1.0, 3.0)).json()
            runs = self.http.get(f"{self.base}/scorecard", timeout=(1.0, 3.0)).json().get("runs", 0) if st.get("state") == "running" else None
            self.last_poll_error = None
        except (requests.RequestException, ValueError) as e:
            self.last_poll_error = type(e).__name__
            return
        phase = st.get("state", "?")
        if phase == "running" and runs is not None and runs > c["baseline"]:
            phase = "restoring"
        with self.lock:
            if self.runs and self.runs[-1]["run_id"] == c["run_id"]:
                self.runs[-1].update(state=st.get("state"), phase=phase, elapsed_s=st.get("elapsed_s", 0.0))


def summary(rev: dict) -> str:
    """One plain-language line for a revealed run: scenario, target, outcome, failed-request %."""
    tr, sc = rev["truth"], rev["score"]
    scen, tgt, failed = tr["scenario"].replace("_", " "), tr["target"], sc.get("failed_request_pct")
    if tr["scenario"] in HEALTHY:
        what = (f"healthy change, no incident" if not sc.get("incidents_opened") else
                f"healthy change, {sc['incidents_opened']} incident(s) opened, {sc.get('actions_executed', 0)} action(s)")
    elif tr["scenario"] == UNSEEN:
        what = ("unseen fault, abstained with no action" if sc.get("abstained_correctly") else
                f"unseen fault, {sc.get('actions_executed', 0)} action(s) executed")
    elif not sc.get("detected"):
        what = "not detected"
    elif sc.get("recovered"):
        what = f"recovered in {sc.get('time_to_verified_recovery_s')} s (EternalAI's own checkout)"
    else:
        what = f"not recovered ({sc.get('final_status') or 'escalated'})"
    return f"{scen} on {tgt}: {what}; {failed}% failed requests."
