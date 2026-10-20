"""Step 3 isolation tests: the LLM report layer is off the recovery path, cannot choose or run an action, falls back to the template, and a provider failure
does not block remediation. Synthetic data only (no network, no Docker). Run against the system checkout:

    PYTHONPATH=<system checkout> python -m pytest tests/test_llm_isolation.py
"""
import re
import threading
import time
from pathlib import Path

import httpx
import pytest

import eternalai.llm as llm
from eternalai.engine import Engine, Incident

PKG = Path(llm.__file__).resolve().parent
CTX = {"cause": "memory_leak", "confidence": 0.9, "candidates": ["recreate_container"], "alternatives": ["latency_spike"],
       "ranking": [{"service": "web", "score": 0.9}], "evidence": [{"id": "e1", "tool": "metrics", "summary": "mem rising"}]}


def bare_engine():
    e = Engine.__new__(Engine)
    e.lock = threading.RLock()
    return e


def test_llm_upgrade_returns_immediately_and_never_holds_the_engine_lock_while_waiting(monkeypatch):
    """A provider that takes 3 s must not delay the caller (the recovery path) and must not hold the engine lock."""
    monkeypatch.setenv("GEMINI_API_KEY", "x")
    release = threading.Event()

    def slow(ctx, client=None):
        release.wait(10)
        return llm.template_report(ctx), {"provider": "gemini", "llm_disagreed": False}
    monkeypatch.setattr("eternalai.engine.make_report", slow)
    e, inc = bare_engine(), Incident("i1", 100.0)
    t0 = time.time()
    e._llm_upgrade_async(inc, CTX)
    assert time.time() - t0 < 0.5                                   # the caller is not blocked
    got = []
    th = threading.Thread(target=lambda: got.append(e.lock.acquire(timeout=1)))   # another thread (the loop) can take the lock meanwhile
    th.start()
    th.join()
    assert got == [True]
    release.set()


def test_report_text_is_replaced_but_the_executed_runbook_is_kept(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "x")
    rep = llm.IncidentReport(summary="s", evidence_ids=["e1"], likely_cause="memory_leak", runbook_id="recreate_container")
    monkeypatch.setattr("eternalai.engine.make_report", lambda ctx, client=None: (rep, {"provider": "gemini", "llm_disagreed": False}))
    e, inc = bare_engine(), Incident("i2", 100.0)
    inc.actions = [{"runbook_id": "restart_service"}]                # what the deterministic policy actually proposed
    inc.log = lambda m: None
    e._llm_upgrade_async(inc, CTX)
    for _ in range(50):
        if inc.report_meta:
            break
        time.sleep(0.05)
    assert inc.report["runbook_id"] == "restart_service" and inc.report_meta["llm_runbook_suggestion"] == "recreate_container"


def test_llm_cannot_choose_a_runbook_outside_the_deterministic_candidates():
    bad = ('{"summary":"x","evidence_ids":["e1"],"likely_cause":"memory_leak","alternative_causes":[],'
           '"runbook_id":"rollback_release","missing_information":[]}')
    with pytest.raises(ValueError):
        llm.validate(bad, CTX)
    with pytest.raises(ValueError):                                  # free text / shell command in an enum field
        llm.validate(bad.replace("rollback_release", "rm -rf /"), CTX)


def test_disagreeing_model_cannot_override_the_engine(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "x")
    out = ('{"summary":"x","evidence_ids":["e1"],"likely_cause":"bad_deploy","alternative_causes":[],'
           '"runbook_id":"recreate_container","missing_information":[]}')
    monkeypatch.setattr(llm, "_gemini", lambda p, c: out)
    rep, meta = llm.make_report(CTX)
    assert meta["llm_disagreed"] and rep.likely_cause == "memory_leak" and rep.runbook_id == "recreate_container"


@pytest.mark.parametrize("exc", [httpx.ConnectTimeout("t"), httpx.ReadTimeout("t"), httpx.ConnectError("down"), httpx.HTTPStatusError("429", request=None, response=None)])
def test_provider_failure_falls_back_to_the_template(monkeypatch, exc):
    monkeypatch.setenv("GEMINI_API_KEY", "x")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setattr(llm, "_gemini", lambda p, c: (_ for _ in ()).throw(exc))
    rep, meta = llm.make_report(CTX)
    assert meta["provider"] == "template" and meta["fallback_reasons"] and rep.runbook_id == "recreate_container"


def test_malformed_output_falls_back(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "x")
    monkeypatch.setattr(llm, "_gemini", lambda p, c: "not json")
    assert llm.make_report(CTX)[1]["provider"] == "template"


def test_every_http_call_has_a_timeout():
    src = Path(llm.__file__).read_text(encoding="utf-8")
    assert len(re.findall(r"client\.post\(", src)) == len(re.findall(r"timeout=20", src)) == 2


def test_policy_executor_verify_and_dedupe_do_not_reference_the_llm_layer():
    """Static code-path check: nothing on the decision/action path imports or calls the LLM module or reads the report."""
    for f in ("policy.py", "executor.py", "verify.py", "dedupe.py", "rca.py", "classify.py", "detect.py"):
        src = (PKG / f).read_text(encoding="utf-8")
        assert not re.search(r"\bllm\b|make_report|\.report\b|GEMINI|GROQ", src), f


def test_engine_decision_does_not_read_the_llm_report_before_proposing():
    src = (PKG / "engine.py").read_text(encoding="utf-8")
    # _diagnose applies the result (propose, then start the LLM thread); _diagnose_compute builds the template report.
    body = src[src.index("    def _diagnose(self"):src.index("def _llm_upgrade_async")]
    apply = body[:body.index("def _diagnose_compute")]
    assert apply.index("self._propose(") < apply.index("self._llm_upgrade_async(")    # propose first, LLM afterwards
    assert "template_report(ctx)" in body and "make_report" not in body                 # deterministic report; LLM not inline
