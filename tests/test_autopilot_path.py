"""The whole automatic path, diagnosis -> policy -> executor, for every diagnosis x service and every runbook x service, under
both rulebooks: the plan's default (eternalai/rulebooks/default.yaml) and the reproduction of the measured benchmark-v2 system.
The expected decisions below are written out by hand from the plan (§6.4, §13.2, §14), not computed by the code under test.
No Docker or Prometheus: the telemetry, ranker, classifier, investigator and executor are fakes, the engine and policy are real."""
import threading

import pytest

from eternalai import config, engine as engine_mod, rulebook
from eternalai.classify import CAUSE_RUNBOOKS, Prediction
from eternalai.engine import Engine, Incident
from eternalai.policy import RUNBOOKS, PolicyEngine

SERVICES = list(config.SERVICES)
RULEBOOKS = {"plan": rulebook.load(rulebook.DEFAULT_FILE, SERVICES),
             "benchmark-v2": rulebook.load(rulebook.RULEBOOK_DIR / "benchmark-v2.yaml", SERVICES)}


def expected(book, runbook, service, fault=None):
    """(risk, autopilot verdict), by hand."""
    if book == "plan":
        risk = {"restart_service": "low", "clear_temp_path": "low", "rollback_release": "high",
                "recreate_container": "low" if service == "web" else "high"}[runbook]
        if fault in ("error_spike", "latency_spike") and risk == "low":
            risk = "medium"
        if service == "payments":                       # protected: always asks
            return risk, "needs_approval"
        return risk, "execute" if risk == "low" else "needs_approval"
    # benchmark-v2: everything low or medium, and autopilot executed low and medium
    risk = "low" if runbook in ("restart_service", "clear_temp_path") or service == "web" else "medium"
    return risk, "execute"


class FakeExecutor:
    def __init__(self):
        self.calls, self.audit = [], []

    def run(self, runbook_id, service, actor, evidence_ids=None, reason=""):
        self.calls.append((runbook_id, service, actor))
        return {"ok": True}


class FakeInvestigator:
    def __init__(self, *a):
        self.items = []

    def __getattr__(self, name):          # metrics, container, error_logs, deploy_history, dependency_failures, forecast, ...
        return lambda *a, **k: None


class FakeRanker:
    def __init__(self, root):
        self.root = root

    def rank(self, table):
        return [{"service": self.root, "score": 0.9}] + [{"service": s, "score": 0.01} for s in SERVICES if s != self.root]


class FakeClassifier:
    abstain_below, gate = 0.4, None

    def __init__(self, label):
        self.label = label

    def predict(self, feats):
        return Prediction(self.label, 0.97, {self.label: 0.97, "healthy": 0.03}, False)


class FakeDockerView:
    def state(self):
        return {}


def make_engine(mode, root, label, monkeypatch, kill_switch=False, protected=None, book="plan"):
    monkeypatch.setattr(engine_mod, "Investigator", FakeInvestigator)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    e = Engine.__new__(Engine)
    e.lock, e.last_error, e.last_closed, e.incidents, e.first_anom = threading.RLock(), None, {}, [], {}
    e.policy = PolicyEngine(mode, rulebook=RULEBOOKS[book], kill_switch=kill_switch,
                            protected=None if protected is None else set(protected))
    e.latest = {}
    e.executor, e.dv, e.detectors, e.prom = FakeExecutor(), FakeDockerView(), None, None
    e.ranker, e.classifier = FakeRanker(root), FakeClassifier(label)
    e.frames = {s: None for s in SERVICES}
    e._depfail = lambda: {}
    e._preserve = lambda inc: None

    def run_now(inc, act, actor):          # the executor stage, synchronously (the real one starts a thread and verifies)
        e.executor.run(act["runbook_id"], act["service"], actor)
        act["executed"] = True
        inc.status = "executing"
    e._run_async = run_now
    return e


def diagnose(e, root):
    inc = Incident("i-" + root, 1000.0)
    inc.services = [root]
    feats = {s: {"up_frac": 1.0} for s in SERVICES}
    e.incidents.append(inc)
    e._try_diagnose(inc, feats, {s: 0.0 for s in SERVICES}, {s: s == root for s in SERVICES})
    return inc


@pytest.mark.parametrize("book", sorted(RULEBOOKS))
@pytest.mark.parametrize("service", SERVICES)
@pytest.mark.parametrize("label", sorted(CAUSE_RUNBOOKS))
def test_autopilot_full_path_every_diagnosis_and_service(label, service, book, monkeypatch):
    e = make_engine("autopilot", service, label, monkeypatch, book=book)
    inc = diagnose(e, service)
    rb = CAUSE_RUNBOOKS[label][0]
    risk, verdict = expected(book, rb, service, label)
    act = inc.actions[-1]
    assert act["runbook_id"] == rb and act["service"] == service and act["risk"] == risk and act["verdict"] == verdict
    if verdict == "execute":
        assert e.executor.calls == [(rb, service, "autopilot")]
    else:
        assert inc.status == "awaiting_approval" and e.executor.calls == []


@pytest.mark.parametrize("book", sorted(RULEBOOKS))
@pytest.mark.parametrize("service", SERVICES)
@pytest.mark.parametrize("runbook", sorted(RUNBOOKS))
def test_autopilot_policy_to_executor_every_runbook_and_service(runbook, service, book, monkeypatch):
    e = make_engine("autopilot", service, "down", monkeypatch, book=book)
    inc = Incident("p", 1000.0)
    inc.likely_cause = "down"
    e.incidents.append(inc)
    e._propose(inc, service, runbook)
    risk, verdict = expected(book, runbook, service, "down")
    assert inc.actions[-1]["verdict"] == verdict and inc.actions[-1]["risk"] == risk
    assert e.executor.calls == ([(runbook, service, "autopilot")] if verdict == "execute" else [])


@pytest.mark.parametrize("service", SERVICES)
def test_high_risk_never_executes_in_any_mode_under_the_plan(service, monkeypatch):
    for mode in ("watch-only", "ask-first", "autopilot"):
        e = make_engine(mode, service, "bad_deploy", monkeypatch)
        inc = diagnose(e, service)
        assert inc.actions[-1]["risk"] == "high" and e.executor.calls == []
        assert inc.actions[-1]["verdict"] == ("observe_only" if mode == "watch-only" else "needs_approval")


@pytest.mark.parametrize("service", SERVICES)
@pytest.mark.parametrize("label", sorted(CAUSE_RUNBOOKS))
def test_protected_service_always_waits_for_approval(label, service, monkeypatch):
    e = make_engine("autopilot", service, label, monkeypatch, protected={service})
    inc = diagnose(e, service)
    assert inc.actions[-1]["verdict"] == "needs_approval" and inc.status == "awaiting_approval" and e.executor.calls == []
    e.approve(inc.id, "dashboard")                       # an approval is the only way it runs
    assert e.executor.calls == [(CAUSE_RUNBOOKS[label][0], service, "human:dashboard")]


def test_payments_is_protected_by_the_plan_rulebook(monkeypatch):
    e = make_engine("autopilot", "payments", "down", monkeypatch)
    inc = diagnose(e, "payments")
    assert "protected" in inc.actions[-1]["reason"] and e.executor.calls == []


@pytest.mark.parametrize("service", SERVICES)
@pytest.mark.parametrize("label", sorted(CAUSE_RUNBOOKS))
def test_kill_switch_blocks_the_whole_path(label, service, monkeypatch):
    e = make_engine("autopilot", service, label, monkeypatch, kill_switch=True)
    assert e.policy.mode == "watch-only"
    inc = diagnose(e, service)
    assert inc.actions[-1]["verdict"] == "blocked" and inc.status == "escalated" and e.executor.calls == []


def test_kill_switch_refuses_a_pending_approval(monkeypatch):
    e = make_engine("autopilot", "orders", "bad_deploy", monkeypatch)
    inc = diagnose(e, "orders")
    assert inc.status == "awaiting_approval"
    e.policy.set_kill_switch(True)
    with pytest.raises(ValueError, match="kill switch"):
        e.approve(inc.id, "dashboard")
    assert e.executor.calls == []
    e.policy.set_kill_switch(False)
    e.approve(inc.id, "dashboard")
    assert e.executor.calls == [("rollback_release", "orders", "human:dashboard")]


def test_abstention_never_reaches_policy_or_executor(monkeypatch):
    e = make_engine("autopilot", "web", "insufficient_evidence", monkeypatch)
    e.classifier.predict = lambda feats: Prediction("insufficient_evidence", 0.5, {"healthy": 0.5}, True, "novel", 9.0)
    inc = diagnose(e, "web")
    assert inc.actions == [] and inc.status == "escalated" and e.executor.calls == []


def test_hourly_cap_stops_autopilot(monkeypatch):
    e = make_engine("autopilot", "web", "down", monkeypatch)
    cap = e.policy.rulebook.max_actions_per_hour
    for i in range(cap):
        e.policy.record_execution(f"x{i}", now=1000.0 + i)    # other names, so no cooldown or breaker applies to web
    d = e.policy.evaluate("restart_service", "web", now=1000.0 + cap)
    assert d.verdict == "blocked" and "hourly cap" in d.reason
    assert e.policy.evaluate("restart_service", "web", now=1000.0 + 3601).verdict == "execute"


def test_cpu_runaway_acts_only_when_users_are_affected(monkeypatch):
    e = make_engine("autopilot", "orders", "down", monkeypatch)
    no = e.policy.evaluate("restart_service", "orders", now=1000.0, fault="cpu_runaway", user_impact=False)
    yes = e.policy.evaluate("restart_service", "orders", now=1000.0, fault="cpu_runaway", user_impact=True)
    assert no.verdict == "observe_only" and yes.verdict == "needs_approval" and yes.risk == "medium"


def test_db_slowdown_is_always_escalated(monkeypatch):
    e = make_engine("autopilot", "orders", "down", monkeypatch)
    d = e.policy.evaluate("restart_service", "orders", now=1000.0, fault="db_slowdown")
    assert d.verdict == "blocked" and "escalated" in d.reason


def test_killswitch_endpoint_needs_the_token_and_returns_to_watch_mode(monkeypatch):
    from fastapi.testclient import TestClient

    from eternalai import api
    monkeypatch.setenv("ETERNALAI_APPROVAL_TOKEN", "test-token-123")
    e = make_engine("autopilot", "web", "down", monkeypatch)
    monkeypatch.setattr(api, "engine", e)
    c = TestClient(api.app)
    assert c.post("/killswitch", json={"on": True}).status_code == 403
    assert c.post("/killswitch", json={"on": True}, headers={"X-Approval-Token": "wrong"}).status_code == 403
    r = c.post("/killswitch", json={"on": True}, headers={"X-Approval-Token": "test-token-123"})
    assert r.status_code == 200 and r.json()["kill_switch"] is True and e.policy.kill_switch is True
    assert e.policy.mode == "watch-only" and r.json()["mode"] == "watch-only"
    h = {"X-Approval-Token": "test-token-123"}
    assert c.post("/mode", json={"mode": "autopilot"}, headers=h).status_code == 409   # cannot leave watch-only while on
    c.post("/killswitch", json={"on": False}, headers=h)
    assert c.post("/mode", json={"mode": "ask"}, headers=h).json() == {"mode": "ask-first"}


class ForestOnlyDetector:
    """High joint score, every single signal inside its learned limits."""
    threshold, limits = 0.5, {}

    def score(self, feats):
        return 0.9

    def out_of_range(self, feats):
        return []


def test_forest_only_anomaly_never_runs_automatically(monkeypatch):
    e = make_engine("autopilot", "web", "down", monkeypatch)
    e.detectors = {"web": ForestOnlyDetector()}
    feats_ok = {"up_frac": 1.0}
    inc = Incident("u", 1000.0)
    inc.services = ["web"]
    e.incidents.append(inc)
    e._try_diagnose(inc, {s: dict(feats_ok) for s in SERVICES}, {s: 0.0 for s in SERVICES}, {s: s == "web" for s in SERVICES})
    act = inc.actions[-1]
    assert inc.diagnosis["anomaly_source"] == "forest_only"
    assert act["verdict"] == "needs_approval" and "unusual combination" in act["reason"] and e.executor.calls == []


def test_anomaly_source():
    from eternalai.detect import anomaly_source

    class Lim(ForestOnlyDetector):
        def out_of_range(self, feats):
            return ["error_ratio"]
    assert anomaly_source(ForestOnlyDetector(), {}, down=True) == "down"
    assert anomaly_source(Lim(), {}, down=False) == "limits"
    assert anomaly_source(ForestOnlyDetector(), {}, down=False) == "forest_only"
    assert anomaly_source(None, {}, down=False) == "none"
