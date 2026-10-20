"""The whole automatic path, diagnosis -> policy -> executor, for every runbook x service: autopilot executes only low-risk
actions; high-risk ones (rollback anywhere, recreate on a stateful service) wait for approval and never reach the executor;
protected services are only observed; the kill switch blocks everything, including approvals. No Docker or Prometheus:
the telemetry, ranker, classifier, investigator and executor are fakes, the engine and policy are real."""
import threading

import pytest

from eternalai import config, engine as engine_mod
from eternalai.classify import CAUSE_RUNBOOKS, Prediction
from eternalai.engine import Engine, Incident
from eternalai.policy import RUNBOOKS, PolicyEngine

SERVICES = list(config.SERVICES)
EXPECTED_RISK = {("restart_service", s): "low" for s in SERVICES} | {("clear_temp_path", s): "low" for s in SERVICES} \
    | {("rollback_release", s): "high" for s in SERVICES} \
    | {("recreate_container", s): ("low" if s == "web" else "high") for s in SERVICES}


class FakeExecutor:
    def __init__(self):
        self.calls, self.audit = [], []

    def run(self, runbook_id, service, actor, evidence_ids=None):
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


def make_engine(mode, root, label, monkeypatch, kill_switch=False, protected=()):
    monkeypatch.setattr(engine_mod, "Investigator", FakeInvestigator)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    e = Engine.__new__(Engine)
    e.lock, e.last_error, e.last_closed, e.incidents, e.first_anom = threading.RLock(), None, {}, [], {}
    e.policy = PolicyEngine(mode, kill_switch=kill_switch, protected=set(protected))
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


@pytest.mark.parametrize("service", SERVICES)
@pytest.mark.parametrize("label", sorted(CAUSE_RUNBOOKS))
def test_autopilot_full_path_every_diagnosis_and_service(label, service, monkeypatch):
    e = make_engine("autopilot", service, label, monkeypatch)
    inc = diagnose(e, service)
    rb = CAUSE_RUNBOOKS[label][0]
    act = inc.actions[-1]
    assert act["runbook_id"] == rb and act["service"] == service and act["risk"] == EXPECTED_RISK[(rb, service)]
    if EXPECTED_RISK[(rb, service)] == "high":
        assert act["verdict"] == "needs_approval" and inc.status == "awaiting_approval" and e.executor.calls == []
    else:
        assert act["verdict"] == "execute" and e.executor.calls == [(rb, service, "autopilot")]


@pytest.mark.parametrize("service", SERVICES)
@pytest.mark.parametrize("runbook", sorted(RUNBOOKS))
def test_autopilot_policy_to_executor_every_runbook_and_service(runbook, service, monkeypatch):
    e = make_engine("autopilot", service, "down", monkeypatch)
    inc = Incident("p", 1000.0)
    e.incidents.append(inc)
    e._propose(inc, service, runbook)
    high = EXPECTED_RISK[(runbook, service)] == "high"
    assert inc.actions[-1]["verdict"] == ("needs_approval" if high else "execute")
    assert e.executor.calls == ([] if high else [(runbook, service, "autopilot")])


@pytest.mark.parametrize("service", SERVICES)
@pytest.mark.parametrize("label", sorted(CAUSE_RUNBOOKS))
def test_protected_service_never_executes_or_asks(label, service, monkeypatch):
    e = make_engine("autopilot", service, label, monkeypatch, protected={service})
    inc = diagnose(e, service)
    assert inc.actions[-1]["verdict"] == "observe_only" and inc.status == "open" and e.executor.calls == []


@pytest.mark.parametrize("service", SERVICES)
@pytest.mark.parametrize("label", sorted(CAUSE_RUNBOOKS))
def test_kill_switch_blocks_the_whole_path(label, service, monkeypatch):
    e = make_engine("autopilot", service, label, monkeypatch, kill_switch=True)
    inc = diagnose(e, service)
    assert inc.actions[-1]["verdict"] == "blocked" and inc.status == "escalated" and e.executor.calls == []


def test_kill_switch_refuses_a_pending_approval(monkeypatch):
    e = make_engine("autopilot", "orders", "bad_deploy", monkeypatch)
    inc = diagnose(e, "orders")
    assert inc.status == "awaiting_approval"
    e.policy.kill_switch = True
    with pytest.raises(ValueError, match="kill switch"):
        e.approve(inc.id, "dashboard")
    assert e.executor.calls == []
    e.policy.kill_switch = False
    e.approve(inc.id, "dashboard")
    assert e.executor.calls == [("rollback_release", "orders", "human:dashboard")]


def test_abstention_never_reaches_policy_or_executor(monkeypatch):
    e = make_engine("autopilot", "web", "insufficient_evidence", monkeypatch)
    e.classifier.predict = lambda feats: Prediction("insufficient_evidence", 0.5, {"healthy": 0.5}, True, "novel", 9.0)
    inc = diagnose(e, "web")
    assert inc.actions == [] and inc.status == "escalated" and e.executor.calls == []


def test_killswitch_endpoint_needs_the_token(monkeypatch):
    from fastapi.testclient import TestClient

    from eternalai import api
    monkeypatch.setenv("ETERNALAI_APPROVAL_TOKEN", "test-token-123")
    e = make_engine("autopilot", "web", "down", monkeypatch)
    monkeypatch.setattr(api, "engine", e)
    c = TestClient(api.app)
    assert c.post("/killswitch", json={"on": True}).status_code == 403
    assert c.post("/killswitch", json={"on": True}, headers={"X-Approval-Token": "wrong"}).status_code == 403
    r = c.post("/killswitch", json={"on": True}, headers={"X-Approval-Token": "test-token-123"})
    assert r.status_code == 200 and r.json() == {"kill_switch": True} and e.policy.kill_switch is True
