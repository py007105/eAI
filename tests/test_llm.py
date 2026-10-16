import json

import httpx
import pytest

from eternalai.llm import make_report, template_report, validate

CTX = {"cause": "memory_leak", "confidence": 0.91, "candidates": ["recreate_container", "restart_service"],
       "ranking": [{"service": "orders", "score": 0.8}], "alternatives": ["bad_deploy"],
       "evidence": [{"id": "ev1", "tool": "metrics", "summary": "mem rising"}]}


def ok(**kw):
    base = {"summary": "orders is leaking memory", "evidence_ids": ["ev1"], "likely_cause": "memory_leak",
            "alternative_causes": [], "runbook_id": "recreate_container", "missing_information": []}
    return json.dumps({**base, **kw})


def test_valid_output_passes():
    assert validate(ok(), CTX).runbook_id == "recreate_container"


@pytest.mark.parametrize("bad", [
    ok(runbook_id="rm -rf /"),                 # not a runbook at all
    ok(runbook_id="rollback_release"),         # real runbook, but not allowed for this cause
    ok(evidence_ids=["ev99"]),                 # invented evidence
    ok(likely_cause="gremlins"),               # outside the label set
    "not json",
])
def test_invalid_output_rejected(bad):
    with pytest.raises(ValueError):
        validate(bad, CTX)


def test_no_keys_uses_template(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    rep, meta = make_report(CTX)
    assert meta["provider"] == "template" and rep.runbook_id == "recreate_container"


def test_abstain_template_has_no_runbook():
    rep = template_report({**CTX, "cause": "insufficient_evidence", "candidates": []})
    assert rep.runbook_id is None and rep.likely_cause == "insufficient_evidence"


def test_provider_failure_falls_back_and_engine_cause_wins(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "x")
    monkeypatch.setenv("GROQ_API_KEY", "y")
    import eternalai.llm as llm
    monkeypatch.setattr(llm, "_gemini", lambda p, c: (_ for _ in ()).throw(httpx.ConnectError("down")))
    monkeypatch.setattr(llm, "_groq", lambda p, c: ok(likely_cause="bad_deploy", runbook_id="recreate_container"))
    rep, meta = make_report(CTX)
    assert meta["provider"] == "groq" and meta["llm_disagreed"] and rep.likely_cause == "memory_leak"
