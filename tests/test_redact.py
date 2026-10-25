"""Redaction before anything leaves the machine, and the Gemini request shape (key in a header, redacted prompt)."""
import json

import httpx

from engine import llm
from engine.redact import redact


def test_known_secret_values_are_removed(monkeypatch):
    monkeypatch.setenv("CHAOS_TOKEN", "s3cr3t-chaos-value")
    monkeypatch.setenv("ETERNALAI_APPROVAL_TOKEN", "change-me")          # placeholder: nothing to hide, left alone
    out = redact("token mismatch for s3cr3t-chaos-value; please change-me")
    assert "s3cr3t-chaos-value" not in out and "change-me" in out


def test_patterns():
    cases = {
        "postgres://admin:hunter2@db:5432/x": "hunter2",
        "password=hunter2 retry": "hunter2",
        '{"api_key": "abcd1234efgh"}': "abcd1234efgh",
        "Authorization: Bearer abc.def-ghi_jkl123": "abc.def-ghi_jkl123",
        "jwt eyJhbGciOi.eyJzdWIiOiIx.SflKxwRJSMeKKF2QT4": "eyJhbGciOi",
        "key AIzaSyA1234567890abcdefghijklmnopqrstuv": "AIzaSy",
        "aws AKIAIOSFODNN7EXAMPLE": "AKIAIOSFODNN7EXAMPLE",
        "gh ghp_abcdefghijklmnopqrstuvwxyz0123456789": "ghp_abc",
        "bot 123456789:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw1": "AAHdqTcv",
        "user alice@example.com failed": "alice@example.com",
        "from 10.0.3.7 port 80": "10.0.3.7",
        "call +91 98765 43210 now": "98765",
        "card 4111 1111 1111 1111 declined": "4111 1111",
        "session 9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08": "9f86d081884c",
    }
    for text, secret in cases.items():
        assert secret not in redact(text), text


def test_ordinary_log_text_survives():
    line = "ERROR orders: payment call failed after 3 retries (HTTP 503) at 12:04:05, latency 1450 ms"
    assert redact(line) == line
    assert redact("order 1234567890123 total 19.99") == "order 1234567890123 total 19.99"   # not Luhn-valid, kept


def ctx():
    return {"cause": "error_spike", "confidence": 0.9, "candidates": ["restart_service"], "alternatives": [],
            "ranking": [{"service": "orders", "score": 0.9}],
            "evidence": [{"id": "ev1", "tool": "logs",
                          "summary": "ERROR auth failed password=hunter2 for bob@corp.example from 10.1.2.3"}]}


def test_gemini_request_has_no_key_in_url_and_a_redacted_prompt(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "AIzaTESTKEY-not-real-0000000000000000000")
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    seen = {}

    def handler(req: httpx.Request):
        seen["url"], seen["headers"], seen["body"] = str(req.url), dict(req.headers), req.content.decode()
        rep = {"summary": "s", "evidence_ids": ["ev1"], "likely_cause": "error_spike", "alternative_causes": [],
               "runbook_id": "restart_service", "missing_information": []}
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": json.dumps(rep)}]}}]})
    client = httpx.Client(transport=httpx.MockTransport(handler))
    rep, meta = llm.make_report(ctx(), client)
    assert meta["provider"] == "gemini"
    assert "key=" not in seen["url"] and "AIzaTESTKEY" not in seen["url"]
    assert seen["headers"]["x-goog-api-key"].startswith("AIzaTESTKEY")
    assert llm.GEMINI_DEFAULT_MODEL in seen["url"]
    for secret in ("hunter2", "bob@corp.example", "10.1.2.3"):
        assert secret not in seen["body"]
