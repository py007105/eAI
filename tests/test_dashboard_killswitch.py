"""Dashboard kill-switch toggle: flips the current state through POST /killswitch with the typed token; refusals are shown."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "dashboard"))


def test_toggle_flips_the_state_and_reports(monkeypatch):
    import app as dash_app
    sent = []
    monkeypatch.setattr(dash_app.poller, "get", lambda k, d=None: {"kill_switch": False} if k == "status" else d)
    monkeypatch.setattr(dash_app, "post", lambda path, token, body: sent.append((path, token, body)) or (200, {"kill_switch": True}))
    msg = dash_app.toggle_killswitch(1, "tok", "en")
    assert sent == [("/killswitch", "tok", {"on": True})] and "ON" in msg
    monkeypatch.setattr(dash_app.poller, "get", lambda k, d=None: {"kill_switch": True} if k == "status" else d)
    monkeypatch.setattr(dash_app, "post", lambda path, token, body: sent.append((path, token, body)) or (200, {"kill_switch": False}))
    assert "off" in dash_app.toggle_killswitch(2, "tok", "en") and sent[-1][2] == {"on": False}


def test_refusal_is_shown(monkeypatch):
    import app as dash_app
    monkeypatch.setattr(dash_app.poller, "get", lambda k, d=None: {} if k == "status" else d)
    monkeypatch.setattr(dash_app, "post", lambda *a: (403, {"detail": "invalid approval token"}))
    assert "403" in dash_app.toggle_killswitch(1, "", "en")
