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
    # an escalated incident without a close time still counts from when it opened
    assert views.status_line([inc("escalated", t0=now - 10)], [], now)[0] == "escalated"


def test_status_line_never_says_healthy_while_a_service_is_anomalous_or_down():
    anom = {"inventory": {"anomalous": True, "state": {"running": True}}, "web": {"anomalous": False, "state": {"running": True}}}
    assert views.status_line([], [], 0.0, "en", anom) == ("watching", "Unusual metrics on inventory; no open incident.")
    down = {"orders": {"anomalous": False, "state": {"running": False}}}
    assert views.status_line([], [], 0.0, "en", down)[0] == "watching"
    ok = {"web": {"anomalous": False, "state": {"running": True}, "features": {"up_frac": 1.0}}}
    assert views.status_line([], [], 0.0, "en", ok)[0] == "healthy"


def test_status_line_has_hindi_text():
    assert views.status_line([], [], 0, "hi")[1] != views.status_line([], [], 0, "en")[1]


def test_dashboard_ttl_matches_the_brain_default():
    src = (Path(__file__).resolve().parents[1] / "engine" / "config.py").read_text(encoding="utf-8")   # read, not imported (no .env load)
    m = re.search(r'APPROVAL_TTL_S = float\(os.getenv\("ETERNALAI_APPROVAL_TTL_S", "(\d+)"\)\)', src)
    assert m and float(m.group(1)) == views.APPROVAL_TTL_S == 120


def pending(t_prop):
    return inc("awaiting_approval", actions=[{"t": t_prop, "verdict": "needs_approval", "executed": False}])


def test_countdown_shows_seconds_left_and_turns_urgent():
    card = views.approvals([APPROVAL], "en", [pending(1000.0)], now=1033.0)[0]
    assert "Expires in 87 s" in flat(card) and "pending-card" in card.className and "urgent" not in card.className
    card = views.approvals([APPROVAL], "en", [pending(1000.0)], now=1100.0)[0]
    assert "Expires in 20 s" in flat(card) and "urgent" in card.className
    assert views.approval_remaining(APPROVAL, [pending(1000.0)], 1500.0) == 0.0


def test_countdown_says_unknown_when_proposal_time_is_missing():
    card = views.approvals([APPROVAL], "en", [], now=1.0)[0]
    assert t("expires_unknown") in flat(card) and "urgent" not in card.className


def test_page_title_changes_only_while_an_approval_is_pending():
    assert views.page_title([], [], 0) == "EternalAI"
    assert views.page_title([APPROVAL], [pending(1000.0)], 1030.0) == "(90 s) Approval waiting · EternalAI"


def test_layout_has_the_title_sink_and_approvals_card():
    import app as dash_app
    s = str(dash_app.layout())
    assert "approvals_card" in s and "title_sink" in s and "page_title" in s
    assert dash_app.app.config.update_title is None        # Dash's default "Updating..." would overwrite the tab title every refresh


def test_evidence_is_collapsed_by_default_with_a_one_line_summary():
    import app as dash_app
    lay = dash_app.layout()

    def find(n, id_):
        if getattr(n, "id", None) == id_:
            return n
        kids = getattr(n, "children", None)
        for k in (kids if isinstance(kids, (list, tuple)) else [kids]):
            if k is not None and not isinstance(k, str) and (r := find(k, id_)) is not None:
                return r
    d = find(lay, "evidence_details")
    assert d is not None and type(d).__name__ == "Details" and d.open is False
    ev = {"evidence": [{"id": "ev1", "summary": "x" * 100}, {"id": "ev2", "summary": "y"}]}
    s = views.evidence_summary(ev)
    assert s.startswith("2 items · ") and "…" in s and "\n" not in s
    assert views.evidence_summary(None) == t("no_evidence")
