"""UI pass before R5b: no 'proof' wording; plain-language status line; approval countdown, highlight and page title; evidence collapsed by default."""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "dashboard"))
import views  # noqa: E402
from labels import LABELS, t  # noqa: E402


def flat(node):
    out = []

    def walk(n):
        if isinstance(n, (list, tuple)):
            for x in n:
                walk(x)
        elif isinstance(n, (str, int, float)):
            out.append(str(n))
        elif n is not None:
            walk(getattr(n, "children", None))
    walk(node)
    return " ".join(out)


def test_no_proof_wording_in_any_visible_label():
    for lang, d in LABELS.items():
        for k, v in d.items():
            assert not re.search(r"\bproo?f|\bprov(e|ed|es|ing)\b", v, re.I), (lang, k, v)
            assert "प्रमाण" not in v and "सिद्ध" not in v, (lang, k)


def inc(status, closed_t=None, services=("inventory",), cause="disk_fill", t0=1000.0, actions=()):
    return {"id": "i1", "status": status, "opened_t": t0, "closed_t": closed_t, "services": list(services), "likely_cause": cause,
            "actions": list(actions), "evidence": []}


APPROVAL = {"incident_id": "i1", "runbook_id": "restart_service", "service": "orders", "risk": "low", "reason": "ask-first", "report": {}}


def test_status_line_states_from_existing_fields_only():
    now = 2000.0
    assert views.status_line([], [], now)[0] == "healthy"
    assert views.status_line([inc("awaiting_approval")], [APPROVAL], now) == ("waiting", "Waiting for approval: restart_service → orders.")
    assert views.status_line([inc("open")], [], now)[0] == "open"
    assert "checking recovery" in views.status_line([inc("verifying")], [], now)[1]
    assert views.status_line([inc("recovered", closed_t=now - 10)], [], now)[0] == "recovered"
    assert views.status_line([inc("escalated", closed_t=now - 10)], [], now)[0] == "escalated"
    # an old closed incident (idle false alert hours ago) does not keep the line red
    assert views.status_line([inc("escalated", closed_t=now - views.RECENT_S - 1)], [], now)[0] == "healthy"


def test_status_line_has_hindi_text():
    assert views.status_line([], [], 0, "hi")[1] != views.status_line([], [], 0, "en")[1]
