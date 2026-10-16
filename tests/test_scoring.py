import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "evaluator"))
from scoring import aggregate, score_run  # noqa: E402


def truth(scen="memory_leak", target="orders", label="memory_leak", supported=True):
    return {"run_id": "r1", "scenario": scen, "target": target, "expected_label": label,
            "supported": supported, "t_inject": 100.0}


def inc(t=110.0, ranking=("orders", "web"), cause="memory_leak", abstained=False, actions=(), ver=None):
    return {"id": "i", "opened_t": t, "closed_t": t + 30, "status": "recovered", "services": list(ranking),
            "ranking": [{"service": s, "score": 1.0} for s in ranking], "likely_cause": cause,
            "abstained": abstained, "actions": list(actions), "verification": ver}


def act(svc="orders", executed=True):
    return {"t": 115.0, "runbook_id": "recreate_container", "service": svc, "verdict": "execute", "executed": executed}


def test_correct_run():
    r = score_run(truth(), [inc(actions=[act()], ver={"outcome": "recovered", "t": 140.0})], 1.5, 160.0)
    assert r["diagnosis_top1"] and r["cause_correct"] and r["recovered"]
    assert r["time_to_detect_s"] == 10.0 and r["time_to_verified_recovery_s"] == 40.0
    assert r["harmful_interventions"] == 0


def test_wrong_service_action_is_harmful_and_wrong_top1():
    r = score_run(truth(), [inc(ranking=("web", "orders"), actions=[act("web")])], 5.0, 160.0)
    assert not r["diagnosis_top1"] and r["diagnosis_top3"] and r["harmful_interventions"] == 1


def test_undetected_fault():
    r = score_run(truth(), [], 20.0, 160.0)
    assert not r["detected"] and r["time_to_detect_s"] is None and r["final_status"] == "undetected"


def test_healthy_surge_any_alert_is_false_and_action_harmful():
    t = truth("traffic_surge", "web", None)
    clean = score_run(t, [], 0.0, 160.0)
    noisy = score_run(t, [inc(actions=[act("web")])], 0.0, 160.0)
    assert clean["false_alerts"] == 0 and noisy["false_alerts"] == 1 and noisy["harmful_interventions"] == 1


def test_unseen_fault_rewards_abstention():
    t = truth("cpu_burn", "orders", "unseen_fault", supported=False)
    good = score_run(t, [inc(cause="insufficient_evidence", abstained=True)], 3.0, 160.0)
    bad = score_run(t, [inc(cause="memory_leak", abstained=False)], 3.0, 160.0)
    assert good["abstained_correctly"] is True and bad["abstained_correctly"] is False


def test_aggregate_has_mean_and_spread():
    rows = [score_run(truth(), [inc(t=105.0)], 1.0, 160.0), score_run(truth(), [inc(t=115.0)], 3.0, 160.0)]
    a = aggregate(rows)["memory_leak"]
    assert a["time_to_detect_s"]["mean"] == 10.0 and a["time_to_detect_s"]["sd"] == 5.0
