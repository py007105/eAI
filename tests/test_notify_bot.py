"""Tests for engine.notify.bot using httpx.MockTransport."""
import json
import logging
from pathlib import Path

import httpx

from engine.notify.bot import RestTelegramBot


def pending_incident(iid="incident-1", status="awaiting_approval"):
    return {
        "id": iid,
        "status": status,
        "likely_cause": "cpu_burn",
        "services": ["orders"],
        "confidence": 0.95,
        "actions": [{
            "service": "orders",
            "runbook_id": "restart_service",
            "verdict": "needs_approval" if status == "awaiting_approval" else "execute",
        }],
        "report": {"permanent_fix": "scale deployment"},
    }


def make_bot(tmp_path, backend_handler, telegram_handler,
             bot_token="secret-bot-token-12345",
             approval_token="secret-approval-token-999",
             chat_id="12345",
             allowed_user_ids=[777]):
    t_client = httpx.Client(transport=httpx.MockTransport(telegram_handler))
    api_client = httpx.Client(transport=httpx.MockTransport(backend_handler))
    return RestTelegramBot(
        bot_token=bot_token,
        chat_id=chat_id,
        backend_url="http://testbackend",
        approval_token=approval_token,
        allowed_user_ids=allowed_user_ids,
        client=t_client,
        api_client=api_client,
        offset_path=tmp_path / "offset.txt",
    )


def test_new_incident_sends_once_and_state_change_edits(tmp_path):
    backend_state = {
        "status": {"kill_switch": False, "calibration": {"show_probability": False}},
        "approvals": [{"incident_id": "incident-1"}],
        "incidents": [pending_incident("incident-1")],
    }

    def backend_handler(req):
        if req.url.path == "/status":
            return httpx.Response(200, json=backend_state["status"])
        elif req.url.path == "/approvals":
            return httpx.Response(200, json=backend_state["approvals"])
        elif req.url.path == "/incidents":
            return httpx.Response(200, json=backend_state["incidents"])
        return httpx.Response(404)

    telegram_calls = []

    def telegram_handler(req):
        method = req.url.path.rsplit("/", 1)[-1]
        body = json.loads(req.content)
        telegram_calls.append((method, body))
        if method == "sendMessage":
            return httpx.Response(200, json={"ok": True, "result": {"message_id": 101}})
        elif method == "editMessageText":
            return httpx.Response(200, json={"ok": True, "result": {"message_id": 101}})
        return httpx.Response(200, json={"ok": True, "result": True})

    bot = make_bot(tmp_path, backend_handler, telegram_handler)

    # 1. First poll sends new incident once
    bot.poll_api()
    assert len(telegram_calls) == 1
    method, payload = telegram_calls[0]
    assert method == "sendMessage"
    assert payload["chat_id"] == "12345"
    assert "Incident incident-1" in payload["text"]
    assert "reply_markup" in payload
    assert payload["reply_markup"]["inline_keyboard"][0][0]["callback_data"] == "a:incident-1"

    # 2. Second poll without change does nothing
    bot.poll_api()
    assert len(telegram_calls) == 1

    # 3. State change in backend triggers editMessageText
    recovered = pending_incident("incident-1", status="recovered")
    recovered["verification"] = {"outcome": "recovered"}
    recovered["closed_t"] = 1700000000
    backend_state["incidents"] = [recovered]
    backend_state["approvals"] = []

    bot.poll_api()
    assert len(telegram_calls) == 2
    method, payload = telegram_calls[1]
    assert method == "editMessageText"
    assert payload["message_id"] == 101
    assert "Verified healthy" in payload["text"]
    assert payload["reply_markup"] == {"inline_keyboard": []}


def test_buttons_removed_after_leaving_approvals(tmp_path):
    backend_state = {
        "status": {"kill_switch": False, "calibration": {"show_probability": False}},
        "approvals": [{"incident_id": "incident-1"}],
        "incidents": [pending_incident("incident-1")],
    }

    def backend_handler(req):
        path = req.url.path
        if path == "/status":
            return httpx.Response(200, json=backend_state["status"])
        elif path == "/approvals":
            return httpx.Response(200, json=backend_state["approvals"])
        elif path == "/incidents":
            return httpx.Response(200, json=backend_state["incidents"])
        return httpx.Response(404)

    telegram_calls = []

    def telegram_handler(req):
        method = req.url.path.rsplit("/", 1)[-1]
        body = json.loads(req.content)
        telegram_calls.append((method, body))
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 201}})

    bot = make_bot(tmp_path, backend_handler, telegram_handler)

    bot.poll_api()
    assert len(telegram_calls) == 1
    assert telegram_calls[0][0] == "sendMessage"
    assert len(telegram_calls[0][1]["reply_markup"]["inline_keyboard"]) == 1

    # Incident leaves /approvals, but status in /incidents remains awaiting_approval
    backend_state["approvals"] = []

    bot.poll_api()
    assert len(telegram_calls) == 2
    assert telegram_calls[1][0] == "editMessageText"
    assert telegram_calls[1][1]["message_id"] == 201
    # Buttons must be removed
    assert telegram_calls[1][1]["reply_markup"] == {"inline_keyboard": []}


def test_tap_from_wrong_chat_or_user_ignored(tmp_path):
    backend_calls = []

    def backend_handler(req):
        backend_calls.append(req)
        return httpx.Response(200, json={"ok": True})

    answers = []
    updates = [
        # Wrong chat
        {
            "update_id": 1,
            "callback_query": {
                "id": "cb-wrong-chat",
                "message": {"chat": {"id": 99999}},
                "from": {"id": 777, "username": "alice"},
                "data": "a:incident-1",
            },
        },
        # Wrong user
        {
            "update_id": 2,
            "callback_query": {
                "id": "cb-wrong-user",
                "message": {"chat": {"id": 12345}},
                "from": {"id": 888, "username": "intruder"},
                "data": "a:incident-1",
            },
        },
    ]

    def telegram_handler(req):
        method = req.url.path.rsplit("/", 1)[-1]
        body = json.loads(req.content)
        if method == "getUpdates":
            return httpx.Response(200, json={"ok": True, "result": updates})
        elif method == "answerCallbackQuery":
            answers.append(body["text"])
            return httpx.Response(200, json={"ok": True, "result": True})
        return httpx.Response(200, json={"ok": True, "result": True})

    bot = make_bot(tmp_path, backend_handler, telegram_handler, chat_id="12345", allowed_user_ids=[777])
    handled = bot.poll_once()

    # Backend was never called
    assert len(backend_calls) == 0
    assert len(handled) == 2
    assert handled[0]["result"] == "not authorized"
    assert handled[1]["result"] == "not an approver"
    assert answers == ["not authorized", "not an approver"]


def test_kill_switch_refuses_tap(tmp_path):
    backend_calls = []

    def backend_handler(req):
        backend_calls.append(req)
        if req.url.path == "/status":
            return httpx.Response(200, json={"kill_switch": True, "calibration": {"show_probability": False}})
        elif req.url.path == "/approvals":
            return httpx.Response(200, json=[{"incident_id": "incident-1"}])
        elif req.url.path == "/incidents":
            return httpx.Response(200, json=[pending_incident("incident-1")])
        return httpx.Response(200, json={"ok": True})

    answers = []
    updates = [
        {
            "update_id": 1,
            "callback_query": {
                "id": "cb-kill-switch",
                "message": {"chat": {"id": 12345}},
                "from": {"id": 777, "username": "alice"},
                "data": "a:incident-1",
            },
        }
    ]

    def telegram_handler(req):
        method = req.url.path.rsplit("/", 1)[-1]
        body = json.loads(req.content)
        if method == "getUpdates":
            return httpx.Response(200, json={"ok": True, "result": updates})
        elif method == "answerCallbackQuery":
            answers.append(body["text"])
            return httpx.Response(200, json={"ok": True, "result": True})
        elif method == "sendMessage":
            return httpx.Response(200, json={"ok": True, "result": {"message_id": 301}})
        return httpx.Response(200, json={"ok": True, "result": True})

    bot = make_bot(tmp_path, backend_handler, telegram_handler, chat_id="12345", allowed_user_ids=[777])
    bot.poll_api()
    assert bot.kill_switch is True

    handled = bot.poll_once()
    assert len(handled) == 1
    assert handled[0]["result"] == "kill switch is on"
    assert answers == ["kill switch is on"]
    # No POST to /approvals
    assert not any(r.method == "POST" and "/approvals/" in str(r.url) for r in backend_calls)


def test_status_code_mappings_200_409_403_503(tmp_path):
    status_codes_to_test = [
        (200, "done"),
        (409, "already handled/expired"),
        (403, "token refused"),
        (503, "token refused"),
    ]

    for idx, (code, expected_text) in enumerate(status_codes_to_test, 10):
        backend_post_requests = []

        def backend_handler(req):
            if req.method == "POST":
                backend_post_requests.append(req)
                return httpx.Response(code, json={"status": code})
            return httpx.Response(200, json={})

        answers = []
        updates = [
            {
                "update_id": idx,
                "callback_query": {
                    "id": f"cb-{code}",
                    "message": {"chat": {"id": 12345}},
                    "from": {"id": 777, "username": "alice"},
                    "data": "a:incident-1",
                },
            }
        ]

        def telegram_handler(req):
            method = req.url.path.rsplit("/", 1)[-1]
            body = json.loads(req.content)
            if method == "getUpdates":
                return httpx.Response(200, json={"ok": True, "result": updates})
            elif method == "answerCallbackQuery":
                answers.append(body["text"])
                return httpx.Response(200, json={"ok": True, "result": True})
            elif method == "sendMessage":
                return httpx.Response(200, json={"ok": True, "result": {"message_id": 301}})
            return httpx.Response(200, json={"ok": True, "result": True})

        bot = make_bot(tmp_path, backend_handler, telegram_handler,
                       approval_token="my-approval-token", chat_id="12345", allowed_user_ids=[777])
        handled = bot.poll_once()
        assert len(handled) == 1
        assert handled[0]["result"] == expected_text
        assert answers == [expected_text]

        assert len(backend_post_requests) == 1
        req = backend_post_requests[0]
        assert req.url.path == "/approvals/incident-1/approve"
        assert req.headers["X-Approval-Token"] == "my-approval-token"
        assert json.loads(req.content) == {"approver": "telegram:alice"}


def test_token_never_appears_in_any_log_output(tmp_path, caplog):
    bot_token = "secret-bot-token-xyz"
    appr_token = "secret-appr-token-abc"

    def backend_handler(req):
        raise httpx.ConnectError(f"connection failed to {req.url}", request=req)

    def telegram_handler(req):
        raise httpx.ConnectError(f"connection failed to {req.url}", request=req)

    bot = make_bot(tmp_path, backend_handler, telegram_handler,
                   bot_token=bot_token, approval_token=appr_token)

    with caplog.at_level(logging.DEBUG):
        bot.poll_api()
        bot.poll_once()

    assert bot_token not in caplog.text
    assert appr_token not in caplog.text
    assert "api.telegram.org" not in caplog.text
    assert "testbackend" not in caplog.text
    assert "ConnectError" in caplog.text


def test_show_confidence_only_when_calibrated(tmp_path):
    backend_state = {
        "status": {"kill_switch": False, "calibration": {"show_probability": False}},
        "approvals": [],
        "incidents": [pending_incident("incident-1")],
    }

    def backend_handler(req):
        path = req.url.path
        if path == "/status":
            return httpx.Response(200, json=backend_state["status"])
        elif path == "/approvals":
            return httpx.Response(200, json=backend_state["approvals"])
        elif path == "/incidents":
            return httpx.Response(200, json=backend_state["incidents"])
        return httpx.Response(404)

    sent_messages = []

    def telegram_handler(req):
        body = json.loads(req.content)
        sent_messages.append(body.get("text", ""))
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 1}})

    bot = make_bot(tmp_path, backend_handler, telegram_handler)

    # 1. When show_probability is False: no Confidence line
    bot.poll_api()
    assert len(sent_messages) == 1
    assert "Confidence:" not in sent_messages[0]

    # 2. When show_probability is True: Confidence line is present
    backend_state["status"]["calibration"]["show_probability"] = True
    bot.poll_api()
    assert len(sent_messages) == 2
    assert "Confidence: 95%." in sent_messages[1]
