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

REAL_FINAL = r'''{"type":"final","root_cause_service":"web","fault":"web container exited; underlying termination cause undetermined","explanation":"The web container exited with code 137 and had no uptime during the incident window (ev1, ev2). Telemetry did not mark it OOM-killed; it also shows no error log lines, recent deploy, or failing dependency calls (ev2, ev3, ev4, ev5). Memory was at 24% of its limit, with exhaustion forecast much later, so the evidence does not establish memory exhaustion as the cause (ev6). The incident record reports recovery after restart_service, and the latest health check shows web running and non-anomalous. The evidence supports an abrupt container exit, but does not explain what caused it.","evidence_ids":["ev1","ev2","ev3","ev4","ev5","ev6"],"missing_evidence":["Container runtime or host diagnostics explaining exit code 137","Independent post-recovery verification details beyond the incident record"],"confidence":"medium","suggested_runbook":"none","expected_impact":"No additional user-facing change is expected; the latest health check shows web running, so another recovery action is not recommended."}'''   # the agent's actual final answer from the live run on incident 422113cf (10:57 AM IST, 25 Oct 2026)


def test_real_agent_final_answer_validates_and_is_kept(tmp_path):
    inv = make(tmp_path, [])
    inc = {"id": "x", "evidence": [{"id": f"ev{i}", "tool": "t", "service": "web", "summary": "s"} for i in range(1, 8)]}
    raw = json.loads(REAL_FINAL)
    assert len(raw["fault"]) > 60                                   # what the old schema rejected
    f, notes = inv.validate(raw, inc)
    assert f["root_cause_service"] == "web" and f["suggested_runbook"] == "none"
    assert f["evidence_ids"] == ["ev1", "ev2", "ev3", "ev4", "ev5", "ev6"] and notes["unknown_evidence_ids"] == []
    assert inv.policy_check(f, inc)["verdict"] == "no_action_suggested"


def test_overlong_free_text_is_trimmed_not_fatal(tmp_path):
    inv = make(tmp_path, [])
    f, _ = inv.validate(dict(FINAL, fault="x" * 500, explanation="y" * 9000), {"id": "i", "evidence": []})
    assert len(f["fault"]) == 200 and len(f["explanation"]) == 2500


def test_connect_errors_are_retried_but_read_timeouts_are_not(monkeypatch):
    monkeypatch.setattr(client_mod.time, "sleep", lambda s: None)
    calls = {"n": 0}

    def flaky(req):
        calls["n"] += 1
        if calls["n"] < 3:
            raise httpx.ConnectError("boom", request=req)
        return httpx.Response(200, json={"id": "r", "status": "completed", "output_text": "ok"})
    c = Agent37Client(api_key="k", instance_id="x", transport=httpx.MockTransport(flaky))
    assert c.respond("hi")["output_text"] == "ok" and calls["n"] == 3
    always = Agent37Client(api_key="k", instance_id="x", transport=httpx.MockTransport(
        lambda r: (_ for _ in ()).throw(httpx.ConnectError("down", request=r))))
    with pytest.raises(Agent37Error) as e:
        always.respond("hi")
    assert e.value.code == "network"
    reads = {"n": 0}

    def slow(req):
        reads["n"] += 1
        raise httpx.ReadTimeout("slow", request=req)
    with pytest.raises(Agent37Error) as e:
        Agent37Client(api_key="k", instance_id="x", transport=httpx.MockTransport(slow)).respond("hi")
    assert e.value.code == "timeout" and reads["n"] == 1             # never re-sent: the turn may already be running


def test_dashboard_lists_stored_investigations_after_restart():
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "dashboard"))
    import agent37_panel as P
    live = [{"id": "a1", "services": ["web"], "likely_cause": "down", "status": "recovered"}]
    stored = [{"incident_id": "a1", "status": "completed", "fault": "x"},
              {"incident_id": "old9", "status": "completed", "fault": "disk_fill"}]
    opts = P.build_options(live, stored)
    assert [o["value"] for o in opts] == ["a1", "old9"]                    # no duplicate; the old one stays selectable
    assert "stored investigation" in opts[1]["label"] and "disk_fill" in opts[1]["label"]
    assert P.build_options([], []) == []
