"""Tests for eternalai.notify.whoami using httpx.MockTransport."""
import json
import httpx

from eternalai.notify.whoami import get_recent_identities


def test_get_recent_identities_extracts_messages_and_callbacks():
    updates = [
        {
            "update_id": 1,
            "message": {
                "chat": {"id": 12345},
                "from": {"id": 67890, "username": "alice"},
                "text": "/start",
            },
        },
        {
            "update_id": 2,
            "callback_query": {
                "id": "cb1",
                "message": {"chat": {"id": 12345}},
                "from": {"id": 67890, "username": "alice"},
                "data": "a:inc-1",
            },
        },
        {
            "update_id": 3,
            "message": {
                "chat": {"id": -99999},
                "from": {"id": 11111, "username": "bob"},
                "text": "hello",
            },
        },
    ]

    def handler(req):
        return httpx.Response(200, json={"ok": True, "result": updates})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    identities = get_recent_identities("dummy-token", client=client)

    assert len(identities) == 2
    assert identities[0] == {"chat_id": 12345, "user_id": 67890, "username": "alice"}
    assert identities[1] == {"chat_id": -99999, "user_id": 11111, "username": "bob"}


def test_get_recent_identities_handles_api_error_without_raising(capsys):
    def handler(req):
        raise httpx.ConnectError("cannot connect", request=req)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    identities = get_recent_identities("dummy-token", client=client)
    assert identities == []
    captured = capsys.readouterr()
    assert "dummy-token" not in captured.err
    assert "ConnectError" in captured.err
