"""Telegram Bot API calls and button checks, using only httpx.MockTransport."""
import json
import logging

import httpx

from eternalai.notify.telegram import TelegramNotifier


def pending(iid="incident-1"):
    return {"id": iid, "status": "awaiting_approval", "likely_cause": "down", "services": ["web"],
            "actions": [{"service": "web", "runbook_id": "restart_service", "verdict": "needs_approval"}]}


def bot(tmp_path, handler, **kwargs):
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return TelegramNotifier("unit-test-token", "-123", client, offset_path=tmp_path / "offset", **kwargs)


def test_send_and_edit_use_redacted_text_and_pending_keyboard(tmp_path):
    calls = []

    def handler(req):
        calls.append((req.url.path.rsplit("/", 1)[-1], json.loads(req.content)))
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 72}})

    notifier = bot(tmp_path, handler)
    inc = pending()
    inc["report"] = {"permanent_fix": "rotate password=sample-private-value"}
    assert notifier.send_incident(inc) == 72
    method, payload = calls[-1]
    assert method == "sendMessage"
    assert payload["reply_markup"] == {"inline_keyboard": [[
        {"text": "Approve", "callback_data": "a:incident-1"},
        {"text": "Reject", "callback_data": "r:incident-1"},
    ]]}
    assert "sample-private-value" not in payload["text"]
    inc["status"] = "recovered"
    inc["verification"] = {"outcome": "recovered"}
    assert notifier.update_incident(72, inc)
    method, payload = calls[-1]
    assert method == "editMessageText" and payload["message_id"] == 72
    assert payload["reply_markup"] == {"inline_keyboard": []}


def test_keyboard_rejects_nonpending_and_oversized_ids(tmp_path):
    sent = []

    def handler(req):
        sent.append(json.loads(req.content))
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 1}})

    notifier = bot(tmp_path, handler)
    inc = pending("x" * 63)
    notifier.send_incident(inc)
    assert "reply_markup" not in sent[-1]
    inc = pending()
    inc["actions"][-1]["verdict"] = "execute"
    notifier.send_incident(inc)
    assert "reply_markup" not in sent[-1]


def test_callback_requires_chat_approver_valid_data_and_pending_incident(tmp_path):
    updates = []
    calls = []
    answers = []
    valid = {"id": "cb1", "from": {"id": 7}, "message": {"chat": {"id": -123}}, "data": "a:incident-1"}

    def handler(req):
        method = req.url.path.rsplit("/", 1)[-1]
        body = json.loads(req.content)
        if method == "getUpdates":
            return httpx.Response(200, json={"ok": True, "result": updates.pop(0) if updates else []})
        if method == "answerCallbackQuery":
            answers.append(body["text"])
        return httpx.Response(200, json={"ok": True, "result": True})

    notifier = bot(tmp_path, handler, approve=lambda iid, name: calls.append(("approve", iid, name)),
                   reject=lambda iid, name: calls.append(("reject", iid, name)),
                   approver_for=lambda uid: "alice" if uid == 7 else None,
                   is_pending=lambda iid: iid == "incident-1", kill_switch_off=lambda: True)
    variants = [
        (valid, "approved"),
        ({**valid, "id": "cb2", "message": {"chat": {"id": -999}}}, "not authorized"),
        ({**valid, "id": "cb3", "from": {"id": 8}}, "not an approver"),
        ({**valid, "id": "cb4", "data": "a:missing"}, "already handled"),
        ({**valid, "id": "cb5", "data": "bad:data"}, "invalid button"),
        ({**valid, "id": "cb6", "data": "r:incident-1"}, "rejected"),
    ]
    updates.append([{"update_id": n, "callback_query": q} for n, (q, _) in enumerate(variants, 10)])
    assert [row["result"] for row in notifier.poll_once()] == [expected for _, expected in variants]
    assert calls == [("approve", "incident-1", "alice"), ("reject", "incident-1", "alice")]
    assert answers == [expected for _, expected in variants]
    assert (tmp_path / "offset").read_text() == "15"
    assert notifier.poll_once() == []


def test_kill_switch_and_repeated_tap_never_execute(tmp_path):
    updates = [[{"update_id": 1, "callback_query": {
        "id": "cb", "from": {"id": 7}, "message": {"chat": {"id": -123}}, "data": "a:incident-1"}}]]
    calls = []

    def handler(req):
        if req.url.path.endswith("/getUpdates"):
            return httpx.Response(200, json={"ok": True, "result": updates.pop(0) if updates else []})
        return httpx.Response(200, json={"ok": True, "result": True})

    notifier = bot(tmp_path, handler, approve=lambda *_: calls.append(1), reject=lambda *_: calls.append(2),
                   approver_for=lambda _: "alice", is_pending=lambda _: True, kill_switch_off=lambda: False)
    assert notifier.poll_once()[0]["result"] == "kill switch is on"
    assert notifier.poll_once() == []
    assert calls == []


def test_offset_survives_restart(tmp_path):
    payloads = []

    def handler(req):
        body = json.loads(req.content)
        payloads.append(body)
        return httpx.Response(200, json={"ok": True, "result": [{"update_id": 40}] if "offset" not in body else []})

    first = bot(tmp_path, handler)
    assert first.poll_once() == []
    second = bot(tmp_path, handler)
    assert second.poll_once() == []
    assert payloads[-1]["offset"] == 41
    assert payloads[-1]["timeout"] == 25


def test_token_and_url_never_reach_error_or_log_line(tmp_path, caplog):
    token = "unit-test-secret-token"

    def handler(req):
        raise httpx.ConnectError("simulated failure at " + str(req.url), request=req)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    notifier = TelegramNotifier(token, "-123", client, offset_path=tmp_path / "offset")
    with caplog.at_level(logging.DEBUG):
        assert notifier.send_incident(pending()) is None
        assert notifier.poll_once() == []
    assert notifier.last_error == "ConnectError"
    assert token not in caplog.text
    assert "api.telegram.org" not in caplog.text
    assert token not in notifier.last_error


def test_httpx_success_log_does_not_expose_token(tmp_path, caplog):
    token = "unit-test-secret-token"

    def handler(req):
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 1}})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    notifier = TelegramNotifier(token, "-123", client, offset_path=tmp_path / "offset")
    with caplog.at_level(logging.DEBUG):
        assert notifier.send_incident(pending()) == 1
    assert token not in caplog.text
    assert "api.telegram.org" not in caplog.text


def test_start_is_daemon_and_stop_joins(tmp_path):
    def handler(req):
        return httpx.Response(200, json={"ok": True, "result": []})

    notifier = bot(tmp_path, handler)
    notifier.start()
    thread = notifier._thread
    assert thread.daemon
    notifier.start()
    assert notifier._thread is thread
    notifier.stop()
    assert not thread.is_alive()
