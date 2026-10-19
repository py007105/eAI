"""Rehearsal R3 findings: (1) no probability is shown next to an abstained 'insufficient evidence' label; (2) an invalid token gives a friendly message that does not
repeat the token."""
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "dashboard"))
import views  # noqa: E402
from labels import t  # noqa: E402


def flat(node):
    """All text in a Dash component tree."""
    out = []

    def walk(n):
        if isinstance(n, (list, tuple)):
            for x in n:
                walk(x)
        elif isinstance(n, str):
            out.append(n)
        elif n is not None:
            walk(getattr(n, "children", None))
    walk(node)
    return " ".join(out)


def inc(abstained, cause, conf):
    return {"id": "a", "kind": "reactive", "status": "escalated" if abstained else "recovered", "abstained": abstained, "confidence": conf,
            "report": {"summary": "s", "likely_cause": cause, "runbook_id": None, "missing_information": []}, "report_meta": {"provider": "gemini"}}


def test_abstained_incident_shows_no_percentage():
    txt = flat(views.report(inc(True, "insufficient_evidence", 0.9999), "en", True))
    assert "%" not in txt and t("abstained_no_prob") in txt and "insufficient evidence" in txt


def test_abstained_hides_the_number_even_when_calibration_is_not_verified():
    txt = flat(views.report(inc(True, "insufficient_evidence", 0.3), "en", False))
    assert "%" not in txt and t("abstained_no_prob") in txt


def test_a_diagnosed_incident_still_shows_its_calibrated_probability():
    txt = flat(views.report(inc(False, "latency_spike", 0.93), "en", True))
    assert "93% calibrated" in txt
    assert t("prob_hidden") in flat(views.report(inc(False, "latency_spike", 0.93), "en", False))


def test_hindi_labels_exist_for_the_new_keys():
    assert t("abstained_no_prob", "hi") != t("abstained_no_prob", "en") and t("token_invalid", "hi") != t("token_invalid", "en")


def test_invalid_token_gives_a_friendly_message_without_the_token(monkeypatch):
    import app as dash_app
    secret = "abc def\nghi"

    def boom(*a, **k):
        assert k["headers"]["X-Approval-Token"] == secret          # inner whitespace is not stripped, only the ends
        raise requests.exceptions.InvalidHeader(f"Invalid return character in header value: {secret!r}")
    monkeypatch.setattr(dash_app.requests, "post", boom)
    code, body = dash_app.post("/mode", secret, {"mode": "ask-first"})
    assert code == 0 and body["detail"] == t("token_invalid") and "abc" not in body["detail"]


def test_token_is_stripped_at_the_ends(monkeypatch):
    import app as dash_app
    seen = {}

    class R:
        status_code, content = 200, b"{}"

        def json(self):
            return {}
    monkeypatch.setattr(dash_app.requests, "post", lambda *a, **k: seen.update(k) or R())
    dash_app.post("/mode", "  tok\n", {"mode": "x"})
    assert seen["headers"]["X-Approval-Token"] == "tok"


def test_non_latin1_token_gives_the_friendly_message_instead_of_crashing_the_callback(monkeypatch):
    import app as dash_app

    def enc(*a, **k):
        "€".encode("latin-1")
    monkeypatch.setattr(dash_app.requests, "post", enc)
    code, body = dash_app.post("/mode", "tok€n", {"mode": "x"})
    assert code == 0 and body["detail"] == t("token_invalid")


def test_tagline_and_banner_claim_only_internal_verification():
    assert t("app_tagline") == "Detect. Diagnose. Recover. Verify."
    assert t("recovered_banner") == "Verified by EternalAI's own synthetic checkout"
    for lang in ("en", "hi"):
        assert "prov" not in t("recovered_banner", lang).lower() and "Predict" not in t("app_tagline", lang)


def test_forecast_panel_carries_the_caveat():
    import app as dash_app
    assert t("forecast_caveat") in str(dash_app.layout())
