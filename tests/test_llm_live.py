"""Live provider tests: one real request each. Skipped when the provider's key is not present.

    pytest -m live
Each test only checks that a real call returns JSON that passes the strict schema and the backend's rules
(known evidence ids, allowed runbook); it does not judge diagnosis quality. Keys are never printed.
"""
import os

import httpx
import pytest

from engine import config  # noqa: F401  (loads .env)
from engine import llm

CTX = {"cause": "memory_leak", "confidence": 0.93, "candidates": ["recreate_container", "restart_service"],
       "alternatives": ["bad_deploy"], "ranking": [{"service": "inventory", "score": 0.74}],
       "evidence": [{"id": "ev1", "tool": "metrics", "summary": "inventory mem_share=0.71, lat_ratio=4.2"},
                    {"id": "ev2", "tool": "forecast", "summary": "inventory memory rising 118 MB/min; exhaustion in 38-61s"}]}


@pytest.mark.live
@pytest.mark.skipif(not os.getenv("GEMINI_API_KEY"), reason="GEMINI_API_KEY not set")
def test_gemini_returns_schema_valid_report():
    raw = llm._gemini(llm._prompt(CTX), httpx.Client())
    rep = llm.validate(raw, CTX)
    assert rep.likely_cause == "memory_leak" and rep.runbook_id in CTX["candidates"]


@pytest.mark.live
@pytest.mark.skipif(not os.getenv("GROQ_API_KEY"), reason="GROQ_API_KEY not set")
def test_groq_returns_schema_valid_report():
    raw = llm._groq(llm._prompt(CTX), httpx.Client())
    rep = llm.validate(raw, CTX)
    assert rep.runbook_id in CTX["candidates"] or rep.runbook_id is None
