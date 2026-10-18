import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("tri", Path(__file__).resolve().parents[1] / "scripts" / "triage_nonrecoveries.py")
tri = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tri)


def row(arm, scen, seed, final, incidents=(), target="web", t="2026-10-17T23:00:00", rec=False):
    return {"arm": arm, "scenario": scen, "seed": seed, "target": target, "finished_at": t, "incidents": list(incidents),
            "score": {"recovered": rec, "final_status": final}}


def inc(status, cause="x", abst=False, actions=()):
    return {"status": status, "likely_cause": cause, "abstained": abst, "actions": list(actions)}


def test_rules_each_fire_once_and_recovered_and_no_action_are_skipped():
    rows = [
        row("eternalai_ask_first", "crash", 1, "awaiting_approval", [inc("awaiting_approval", actions=[{"runbook_id": "r", "service": "s", "verdict": "needs_approval", "approved_by": None}])], t="2026-10-17T23:10:00"),
        row("eternalai_ask_first", "latency", 2, "undetected", t="2026-10-17T23:20:00"),
        row("eternalai_autopilot", "crash", 3, "escalated", [inc("escalated", "insufficient_evidence", True)], target="orders"),
        row("eternalai_autopilot", "crash", 4, "escalated", [inc("escalated", actions=[{"runbook_id": "restart_service", "service": "s", "verdict": "blocked", "reason": "cooldown: last action on s was 85s ago"}])]),
        row("prototype_rules", "latency", 5, "verifying", [inc("verifying")]),
        row("threshold_restart", "latency", 6, "undetected"),
        row("threshold_restart", "disk_fill", 7, "unresolved", [inc("unresolved")]),
        row("eternalai_autopilot", "latency", 8, "recovered", rec=True),
        row("no_action", "latency", 9, "undetected"),
        row("eternalai_autopilot", "traffic_surge", 10, "escalated"),
    ]
    got = {x["seed"]: x["class"] for x in tri.classify(rows)}
    assert got == {1: "b", 2: "b", 3: "c", 4: "a", 5: "a", 6: "c", 7: "c"}


def test_ask_first_runs_before_the_stuck_proposal_are_not_blamed_on_it():
    rows = [row("eternalai_ask_first", "latency", 1, "undetected", t="2026-10-17T22:00:00"),
            row("eternalai_ask_first", "crash", 2, "awaiting_approval", [inc("awaiting_approval", actions=[{"runbook_id": "r", "service": "s", "verdict": "needs_approval", "approved_by": None}])], t="2026-10-17T23:00:00")]
    got = {x["seed"]: x["class"] for x in tri.classify(rows)}
    assert got == {1: "c", 2: "b"}
