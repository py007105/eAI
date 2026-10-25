"""Agent37 investigator: all HTTP is a mock transport here (no network, no credit spent)."""
import json
import threading
import time

import httpx
import pytest

from engine.agent37 import client as client_mod
from engine.agent37.client import Agent37Client, Agent37Error
from engine.agent37.investigator import Investigator, _json_from
from engine.agent37.views import graph, twin
from engine.policy import PolicyEngine


class Inc:
    def __init__(self, iid, status="awaiting_approval", cause="bad_deploy", services=("payments",)):
        self.id, self.status, self.likely_cause, self.services = iid, status, cause, list(services)

    def public(self):
        return {"id": self.id, "kind": "reactive", "status": self.status, "services": self.services,
                "likely_cause": self.likely_cause, "confidence": 0.9, "abstained": False, "ranking": [],
                "diagnosis": {"root": self.services[0]}, "before": {}, "after": {}, "timeline": [{"t": 1, "msg": "opened"}],
                "opened_t": 1.0, "verification": None,
                "actions": [{"runbook_id": "rollback_release", "service": "payments", "verdict": "needs_approval",
                             "risk": "high", "reason": "protected", "executed": False}],
                "evidence": [{"id": "ev1", "tool": "metrics", "service": "payments", "summary": "5xx 70%"},
                             {"id": "ev2", "tool": "deploys", "service": "payments", "summary": "release v3-bad"}]}


class Eng:
    def __init__(self):
        self.lock = threading.RLock()
        self.incidents = [Inc("inc1")]
        self.latest = {"payments": {"score": 0.9, "anomalous": True, "state": {"running": True}, "features": {"error_ratio": 0.7}},
                       "web": {"score": 0.3, "anomalous": False, "state": {"running": True}, "features": {}}}
        self.depfail = {("orders", "payments"): 0.6}
        self.policy = PolicyEngine(mode="ask-first")


def transport(replies, seen=None, status=200):
    it = iter(replies)

    def handler(req: httpx.Request):
        if seen is not None:
            seen.append((req.url.path, req.headers.get("X-Agent37-Key"), json.loads(req.content or b"{}")))
        if req.url.path.endswith("/budget"):
            return httpx.Response(200, json={"monthly_cap_micros": 3000000, "monthly_consumed_micros": 1000,
                                             "monthly_remaining_micros": 2999000})
        if status != 200:
            return httpx.Response(status, json={"error": {"code": "instance_budget_exhausted"}})
        text = next(it)
        return httpx.Response(200, json={"id": "r1", "session_id": "s1", "status": "completed", "output_text": text,
                                         "usage": {"input_tokens": 100, "output_tokens": 20, "cost_usd": 0.0004}})
    return httpx.MockTransport(handler)


def make(tmp_path, replies, seen=None, status=200, eng=None):
    c = Agent37Client(api_key="k-test", instance_id="abc", transport=transport(replies, seen, status))
    return Investigator(eng or Eng(), client=c, store_path=tmp_path / "inv.json")


def wait(inv, iid, timeout=5):
    end = time.time() + timeout
    while time.time() < end:
        if inv.records[iid]["status"] not in ("queued", "running"):
            return inv.records[iid]
        time.sleep(0.02)
    raise AssertionError("investigation did not finish")


FINAL = {"type": "final", "root_cause_service": "payments", "fault": "bad_deploy",
         "explanation": "Errors began with release v3-bad.", "evidence_ids": ["ev1", "ev2", "ev99"],
         "missing_evidence": ["logs"], "confidence": "medium", "suggested_runbook": "rollback_release",
         "expected_impact": "checkout recovers"}


def test_tool_loop_then_validated_final_and_policy(tmp_path):
    seen = []
    inv = make(tmp_path, ['{"type":"tool_call","tool":"get_service_health","args":{"service":"payments"}}',
                          "Here you go: " + json.dumps(FINAL)], seen)
    rec = wait(inv, inv.start("inc1")["incident_id"])
    assert rec["status"] == "completed"
    assert [s["kind"] for s in rec["steps"]] == ["agent_turn", "tool", "agent_turn"]
    assert rec["finding"]["evidence_ids"] == ["ev1", "ev2"]                      # invented id dropped
    assert rec["validation"]["unknown_evidence_ids"] == ["ev99"]
    assert rec["policy"]["verdict"] == "needs_approval"                          # payments is protected
    assert rec["policy"]["authority"] == "EternalAI policy engine"
    assert rec["policy"]["agrees_with_engine"] is True
    assert seen[0][0] == "/v1/responses" and seen[0][1] == "k-test"
    assert seen[1][2]["session_id"] == "s1"                                       # same session for the tool result
    assert "<data>" in seen[0][2]["input"] and "untrusted" in seen[0][2]["input"]
    assert inv.reported_cost_usd() == pytest.approx(0.0008)


def test_agent_cannot_change_policy_state_or_execute(tmp_path):
    eng = Eng()
    before = (list(eng.policy.executed), dict(eng.policy.history), set(eng.policy.breaker_open))
    inv = make(tmp_path, [json.dumps(FINAL)], eng=eng)
    rec = wait(inv, inv.start("inc1")["incident_id"])
    assert rec["status"] == "completed"
    assert (list(eng.policy.executed), dict(eng.policy.history), set(eng.policy.breaker_open)) == before
    assert eng.incidents[0].status == "awaiting_approval"                         # nothing approved or executed


def test_unknown_runbook_is_never_passed_on(tmp_path):
    bad = dict(FINAL, suggested_runbook="rm -rf /")
    inv = make(tmp_path, [json.dumps(bad)])
    rec = wait(inv, inv.start("inc1")["incident_id"])
    assert rec["finding"]["suggested_runbook"] == "none"
    assert rec["validation"]["rejected_runbook"] == "rm -rf /"
    assert rec["policy"]["verdict"] == "no_action_suggested"


def test_unknown_service_is_invalid_output(tmp_path):
    inv = make(tmp_path, [json.dumps(dict(FINAL, root_cause_service="database"))])
    rec = wait(inv, inv.start("inc1")["incident_id"])
    assert rec["status"] == "failed" and rec["error"].startswith("invalid_agent_output")


def test_budget_exhausted_degrades_gracefully(tmp_path):
    inv = make(tmp_path, [], status=402)
    rec = wait(inv, inv.start("inc1")["incident_id"])
    assert rec["status"] == "budget_blocked" and "budget_exhausted" in rec["error"]


def test_not_configured_and_local_budget(tmp_path, monkeypatch):
    inv = Investigator(Eng(), client=Agent37Client(api_key="", instance_id=""), store_path=tmp_path / "a.json")
    assert inv.start("inc1")["status"] == "not_configured"
    monkeypatch.setenv("AGENT37_LOCAL_BUDGET_USD", "0.0001")
    inv2 = make(tmp_path / "b", [json.dumps(FINAL)])
    inv2.records["old"] = {"status": "completed", "steps": [{"cost_usd": 0.01}]}
    assert inv2.start("inc1")["status"] == "budget_blocked"


def test_persists_across_restart_and_dedupes(tmp_path):
    inv = make(tmp_path, [json.dumps(FINAL)])
    wait(inv, inv.start("inc1")["incident_id"])
    again = make(tmp_path, [])                                                    # a new process reads the file
    assert again.records["inc1"]["status"] == "completed"
    assert again.start("inc1")["status"] == "completed"                           # unchanged incident: no new paid run
    assert len(again.records["inc1"]["steps"]) == 1


def test_client_maps_errors():
    c = Agent37Client(api_key="k", instance_id="x", transport=httpx.MockTransport(
        lambda r: httpx.Response(503, json={"error": {"code": "wake_timeout"}})))
    with pytest.raises(Agent37Error) as e:
        c.respond("hi")
    assert e.value.code == "wake_timeout"
    failed = Agent37Client(api_key="k", instance_id="x", transport=httpx.MockTransport(
        lambda r: httpx.Response(200, json={"status": "failed", "error": {"code": "model_error", "message": "x"}})))
    with pytest.raises(Agent37Error) as e:
        failed.respond("hi")
    assert e.value.code == "turn_failed"
    assert client_mod.Agent37Client(api_key="", instance_id="").configured is False


def test_json_extraction():
    assert _json_from('```json\n{"type": "final", "a": "}"}\n```') == {"type": "final", "a": "}"}
    assert _json_from("no json here") is None


def test_twin_and_graph_have_real_state_and_suspected_causes(tmp_path):
    inv = make(tmp_path, [json.dumps(FINAL)])
    wait(inv, inv.start("inc1")["incident_id"])
    t = twin(inv.engine, inv)
    assert t["services"]["payments"]["health"] == "anomalous"
    assert t["services"]["payments"]["active_incidents"] == ["inc1"]
    assert t["services"]["payments"]["last_agent37_investigation"]["fault"] == "bad_deploy"
    assert t["services"]["inventory"]["health"] == "unknown"                      # no telemetry stays unknown
    g = graph(inv.engine, inv)
    types = {e["type"] for e in g["edges"]}
    assert {"DEPENDS_ON", "AFFECTED_BY", "SUSPECTED_CAUSE", "PROPOSED_ACTION"} <= types
    assert "CONFIRMED_CAUSE" not in types
    assert any(e["source"] == "Agent37 (advisory)" for e in g["edges"])


def test_api_routes_contract(tmp_path, monkeypatch):
    from fastapi import HTTPException
    from engine import api
    monkeypatch.setattr(api, "engine", Eng())
    monkeypatch.setattr(api, "_inv", make(tmp_path, [json.dumps(FINAL)], eng=api.engine))
    monkeypatch.setenv("ETERNALAI_APPROVAL_TOKEN", "secret-token-for-test")
    with pytest.raises(HTTPException) as e:
        api.agent37_investigate("inc1", x_approval_token=None)          # spending credit needs the operator token
    assert e.value.status_code == 403
    with pytest.raises(HTTPException) as e:
        api.agent37_investigate("nope", x_approval_token="secret-token-for-test")
    assert e.value.status_code == 404
    rec = api.agent37_investigate("inc1", x_approval_token="secret-token-for-test")
    wait(api._inv, rec["incident_id"])
    view = api.agent37_investigation("inc1")
    assert view["engine_pipeline"]["source"].startswith("EternalAI engine")
    assert api.agent37_status()["instance_budget"]["monthly_remaining_micros"] == 2999000
    assert api.agent37_investigations()[0]["fault"] == "bad_deploy"
    assert "services" in api.agent37_twin() and "edges" in api.agent37_graph()
    assert "k-test" not in json.dumps([view, api.agent37_status()])            # the key never leaves the server
