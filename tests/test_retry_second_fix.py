"""Retry once with the second candidate fix after a failed verification, then escalate (plan P8/L5: max 2 attempts).

Real engine and policy (plan rulebook, eternalai/rulebooks/default.yaml); fakes for telemetry, ranker, classifier, executor
and the verification probe. Expected candidates are the fixed table (no knowledge base loaded):
down -> restart_service, recreate_container; disk_fill -> clear_temp_path only."""
import threading
from types import SimpleNamespace

from eternalai import config, engine as engine_mod, rulebook
from eternalai.classify import Prediction
from eternalai.engine import Engine, Incident
from eternalai.policy import PolicyEngine

SERVICES = list(config.SERVICES)
PLAN = rulebook.load(rulebook.DEFAULT_FILE, SERVICES)


class FakeExecutor:
    def __init__(self):
        self.calls = []

    def run(self, runbook_id, service, actor, evidence_ids=None, reason=""):
        self.calls.append((runbook_id, service, actor))
        return {"ok": True}


class FakeInvestigator:
    def __init__(self, *a):
        self.items = []

    def __getattr__(self, name):
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


def make(monkeypatch, root, label, outcomes, kill_after_first=False):
    """Engine whose verification returns `outcomes` in order; actions run synchronously."""
    monkeypatch.setattr(engine_mod, "Investigator", FakeInvestigator)
    monkeypatch.setattr(engine_mod, "remember_verified", lambda *a, **k: None)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    sleeps, clock = [], [1_000_000.0]       # a fake clock: sleeping advances it, so the policy sees the cooldown pass

    def sleep(s):
        sleeps.append(s)
        clock[0] += s
    monkeypatch.setattr(engine_mod.time, "sleep", sleep)
    monkeypatch.setattr(engine_mod.time, "time", lambda: clock[0])
    e = Engine.__new__(Engine)
    e.lock, e.last_error, e.last_closed, e.incidents, e.first_anom = threading.RLock(), None, {}, [], {}
    e.policy = PolicyEngine("autopilot", rulebook=PLAN)
    e.latest, e.persist = {}, SimpleNamespace(runs=[])
    e.executor, e.dv, e.detectors, e.prom = FakeExecutor(), SimpleNamespace(state=lambda: {}), None, None
    e.ranker, e.classifier = FakeRanker(root), FakeClassifier(label)
    e.frames = {s: None for s in SERVICES}
    e._depfail = lambda: {}
    e._preserve = lambda inc: None
    e._app_snapshot = lambda probe: {}
    queue = list(outcomes)

    def verify(_s):
        out = queue.pop(0)
        if kill_after_first:
            e.policy.set_kill_switch(True)
        return {"outcome": out, "probes": 20, "success_rate": 1.0 if out == "recovered" else 0.2}
    monkeypatch.setattr(engine_mod, "verify_recovery", verify)

    def run_now(inc, act, actor):
        inc.status = "executing"
        e._act_and_verify(inc, act, actor)
    e._run_async = run_now
    return e, sleeps


def diagnose(e, root):
    inc = Incident("i-" + root, 1000.0)
    inc.services = [root]
    e.incidents.append(inc)
    e._try_diagnose(inc, {s: {"up_frac": 1.0} for s in SERVICES}, {s: 0.0 for s in SERVICES},
                    {s: s == root for s in SERVICES})
    return inc


def test_failed_fix_retries_the_second_candidate_once_and_can_recover(monkeypatch):
    e, sleeps = make(monkeypatch, "web", "down", ["unresolved", "recovered"])
    inc = diagnose(e, "web")
    assert e.executor.calls == [("restart_service", "web", "autopilot"), ("recreate_container", "web", "autopilot")]
    assert inc.status == "recovered"
    assert [a["verification"]["outcome"] for a in inc.actions] == ["unresolved", "recovered"]
    assert any("retrying once with the second candidate recreate_container" in t["msg"] for t in inc.timeline)
    assert sleeps and 0 < max(sleeps) <= PLAN.cooldown_s + 1   # waited out the cooldown, did not bypass it


def test_second_failure_escalates_after_exactly_two_attempts(monkeypatch):
    e, _ = make(monkeypatch, "web", "down", ["unresolved", "partially_recovered"])
    inc = diagnose(e, "web")
    assert len(e.executor.calls) == 2 and inc.status == "escalated"
    assert any("escalated to a human" in t["msg"] for t in inc.timeline)
    assert "web" in e.policy.breaker_open or len(e.policy.history["web"]) == PLAN.max_unverified_actions_per_service


def test_retry_still_needs_approval_when_the_rulebook_says_so(monkeypatch):
    # recreate_container on orders is high risk under the plan: the retry waits for a human
    e, _ = make(monkeypatch, "orders", "down", ["unresolved", "recovered"])
    inc = diagnose(e, "orders")
    assert e.executor.calls == [("restart_service", "orders", "autopilot")]
    assert inc.status == "awaiting_approval" and inc.actions[-1]["verdict"] == "needs_approval"
    e.approve(inc.id, "dashboard")
    assert e.executor.calls[-1] == ("recreate_container", "orders", "human:dashboard") and inc.status == "recovered"


def test_kill_switch_blocks_the_retry(monkeypatch):
    e, _ = make(monkeypatch, "web", "down", ["unresolved"], kill_after_first=True)
    inc = diagnose(e, "web")
    assert e.executor.calls == [("restart_service", "web", "autopilot")]
    assert inc.status == "escalated" and inc.actions[-1]["verdict"] == "blocked"


def test_single_candidate_keeps_the_old_behaviour(monkeypatch):
    e, sleeps = make(monkeypatch, "web", "disk_fill", ["unresolved"])     # clear_temp_path is the only candidate
    inc = diagnose(e, "web")
    assert len(e.executor.calls) == 1 and inc.status == "unresolved" and len(inc.actions) == 1
    assert sleeps == [3]        # only the existing pause before verification
