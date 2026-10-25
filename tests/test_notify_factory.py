"""Notifier selection and queued state-change delivery."""
import json
import time

import httpx

from engine.notify import NullNotifier, TelegramNotifier, make_notifier


def callbacks():
    return (lambda *_: None, lambda *_: None, lambda _: "alice")


def test_missing_or_blank_configuration_is_a_noop():
    for env in ({}, {"TELEGRAM_BOT_TOKEN": "  ", "TELEGRAM_CHAT_ID": "123"},
                {"TELEGRAM_BOT_TOKEN": "test-token", "TELEGRAM_CHAT_ID": "  "}):
        notifier = make_notifier(*callbacks(), env=env)
        assert isinstance(notifier, NullNotifier)
        assert notifier.incident_changed({"id": "i"}) is None
        assert notifier.start() is None
        assert notifier.stop() is None


def test_nonnumeric_chat_id_is_refused_without_repeating_its_value():
    notifier = make_notifier(*callbacks(), env={"TELEGRAM_BOT_TOKEN": "test-token", "TELEGRAM_CHAT_ID": "bad-value"})
    assert isinstance(notifier, NullNotifier)
    assert notifier.reason == "TELEGRAM_CHAT_ID is not a number"
    assert "bad-value" not in notifier.reason


def test_factory_makes_no_request_and_starts_no_thread():
    notifier = make_notifier(*callbacks(), env={"TELEGRAM_BOT_TOKEN": "test-token", "TELEGRAM_CHAT_ID": " -123 "})
    assert isinstance(notifier, TelegramNotifier)
    assert notifier.chat_id == "-123"
    assert notifier._thread is None and notifier._delivery_thread is None
    notifier.stop()


def _wait_for_count(items, count):
    deadline = time.monotonic() + 2
    while len(items) < count and time.monotonic() < deadline:
        time.sleep(0.01)
    assert len(items) == count


def test_only_visible_state_changes_edit_the_original_message(tmp_path):
    calls = []

    def handler(req):
        method = req.url.path.rsplit("/", 1)[-1]
        calls.append((method, json.loads(req.content)))
        result = {"message_id": 55} if method == "sendMessage" else True
        return httpx.Response(200, json={"ok": True, "result": result})

    notifier = TelegramNotifier("test-token", -123, httpx.Client(transport=httpx.MockTransport(handler)),
                                offset_path=tmp_path / "offset")
    # Keep this test about delivery; callback polling is covered in test_telegram.py.
    notifier.poll_once = lambda: notifier._stop.wait(0.01)
    notifier.start()
    try:
        incident = {"id": "i1", "status": "awaiting_approval", "likely_cause": "down",
                    "actions": [{"runbook_id": "restart_service", "service": "web", "verdict": "needs_approval",
                                 "approved_by": None}], "verification": None}
        notifier.incident_changed(incident)
        _wait_for_count(calls, 1)
        assert calls[0][0] == "sendMessage"

        incident["report"] = {"summary": "new wording"}
        notifier.incident_changed(incident)
        assert notifier._send_queue.empty()
        assert len(calls) == 1

        incident["actions"][-1]["approved_by"] = "alice"
        notifier.incident_changed(incident)
        _wait_for_count(calls, 2)
        assert calls[-1][0] == "editMessageText" and calls[-1][1]["message_id"] == 55

        incident["actions"][-1]["verdict"] = "execute"
        notifier.incident_changed(incident)
        _wait_for_count(calls, 3)

        incident["status"] = "recovered"
        notifier.incident_changed(incident)
        _wait_for_count(calls, 4)

        incident["verification"] = {"outcome": "recovered"}
        notifier.incident_changed(incident)
        _wait_for_count(calls, 5)
        assert [method for method, _ in calls] == ["sendMessage"] + ["editMessageText"] * 4
    finally:
        notifier.stop()


def test_failed_send_allows_retry_of_the_same_state(tmp_path):
    calls = []

    def handler(req):
        calls.append(1)
        return httpx.Response(200, json={"ok": len(calls) > 1, "result": {"message_id": 5}})

    notifier = TelegramNotifier("test-token", -123, httpx.Client(transport=httpx.MockTransport(handler)),
                                offset_path=tmp_path / "offset")
    notifier.poll_once = lambda: notifier._stop.wait(0.01)
    notifier.start()
    try:
        incident = {"id": "i1", "status": "escalated", "actions": []}
        notifier.incident_changed(incident)
        _wait_for_count(calls, 1)
        deadline = time.monotonic() + 2
        while notifier._visible_states and time.monotonic() < deadline:
            time.sleep(0.01)
        assert not notifier._visible_states
        notifier.incident_changed(incident)
        _wait_for_count(calls, 2)
    finally:
        notifier.stop()
