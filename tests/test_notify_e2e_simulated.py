"""Live demonstration test for Telegram bot notifications and approval tap."""
from __future__ import annotations

import json
import logging
import os
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest

pytest.importorskip("playwright")   # playwright is not in requirements: skip this module where it is not installed

import uvicorn
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from playwright.sync_api import sync_playwright

from eternalai.notify.bot import RestTelegramBot
from eternalai.notify.format import format_incident
from eternalai.redact import redact

ROOT = Path(__file__).resolve().parents[1]
SHOTS_DIR = ROOT / "docs" / "screenshots"


class ApproverBody(BaseModel):
    approver: str = "operator"


def create_live_app(state: dict, approval_token: str):
    app = FastAPI(title="LiveBackendMock")

    @app.get("/status")
    def get_status():
        return {
            "mode": "ask-first",
            "brain": "eternalai",
            "models": {"detectors": True, "classifier": True, "ranker": True, "baselines": True},
            "fallbacks_in_use": [],
            "calibration": {"ece": 0.02, "show_probability": True, "data_hash": "c1a2"},
            "breakers_open": [],
            "last_error": None,
            "last_error_t": None,
            "kill_switch": state.get("kill_switch", False),
            "protected_services": ["payments"],
            "policy": {"mode": "ask-first", "breakers_open": [], "protected": ["payments"], "approvers": []},
            "open_incidents": 1 if state.get("status") == "awaiting_approval" else 0,
        }

    @app.get("/services")
    def get_services():
        anom = state.get("status") == "awaiting_approval"
        return {
            "services": {
                "web": {"features": {"lat_ratio": 1.0, "rps_ratio": 1.0, "error_ratio": 0.0, "mem_share": 0.2, "up_frac": 1.0},
                        "score": 0.1, "anomalous": False, "state": {"running": True, "image_tag": "v1"}},
                "orders": {"features": {"lat_ratio": 4.5 if anom else 1.0, "rps_ratio": 1.0, "error_ratio": 0.4 if anom else 0.0,
                                        "mem_share": 0.72 if anom else 0.25, "up_frac": 1.0},
                           "score": 3.8 if anom else 0.2, "anomalous": anom, "state": {"running": True, "image_tag": "v1"}},
                "inventory": {"features": {"lat_ratio": 1.0, "rps_ratio": 1.0, "error_ratio": 0.0, "mem_share": 0.3, "up_frac": 1.0},
                              "score": 0.2, "anomalous": False, "state": {"running": True, "image_tag": "v1"}},
                "payments": {"features": {"lat_ratio": 1.0, "rps_ratio": 1.0, "error_ratio": 0.0, "mem_share": 0.25, "up_frac": 1.0},
                             "score": 0.1, "anomalous": False, "state": {"running": True, "image_tag": "v1"}},
            },
            "topology": {"web": ["orders", "inventory"], "orders": ["inventory", "payments"], "inventory": [], "payments": []},
            "depfail": {},
        }

    @app.get("/approvals")
    def get_approvals():
        if state.get("status") == "awaiting_approval":
            return [{
                "incident_id": state["id"],
                "service": "orders",
                "runbook_id": "restart_service",
                "risk": "low",
                "reason": "ask-first: service down requires approval",
                "report": state["report"],
            }]
        return []

    @app.get("/incidents")
    def get_incidents():
        return [state]

    @app.get("/scorecard")
    def get_scorecard():
        return {"runs": []}

    @app.post("/approvals/{iid}/approve")
    def post_approve(iid: str, who: ApproverBody, x_approval_token: str | None = Header(None)):
        if not x_approval_token or x_approval_token != approval_token:
            raise HTTPException(403, "invalid approval token")
        if state.get("status") != "awaiting_approval":
            raise HTTPException(409, "incident already handled or not awaiting approval")

        state["status"] = "recovered"
        state["closed_t"] = time.time()
        state["actions"][-1]["executed"] = True
        state["actions"][-1]["approved_by"] = who.approver
        state["verification"] = {"outcome": "recovered", "success_rate": 1.0, "probes": 10, "t": time.time()}
        return {"ok": True}

    return app


def test_step4_live_flow_and_screenshots(tmp_path):
    SHOTS_DIR.mkdir(parents=True, exist_ok=True)
    approval_token = "live-demo-approval-token-42"
    now = time.time()

    initial_incident = {
        "id": "inc-live-101",
        "opened_t": now - 40,
        "closed_t": None,
        "status": "awaiting_approval",
        "likely_cause": "down",
        "services": ["orders"],
        "confidence": 0.96,
        "abstained": False,
        "actions": [{
            "t": now - 35,
            "service": "orders",
            "runbook_id": "restart_service",
            "verdict": "needs_approval",
            "reason": "ask-first: low-risk action requires approval",
            "risk": "low",
            "executed": False,
            "approved_by": None,
        }],
        "report": {
            "summary": "orders shows signs of down (classifier confidence 0.96). Proposed runbook: restart_service. Recovery is only confirmed after the synthetic checkout passes.",
            "permanent_fix": "scale deployment replicas",
            "runbook_id": "restart_service",
        },
        "diagnosis": {"root": "orders", "limits_exceeded": ["up_frac"]},
        "verification": None,
    }

    state = dict(initial_incident)
    app = create_live_app(state, approval_token)

    # 1. Start live backend server
    config = uvicorn.Config(app, host="127.0.0.1", port=8125, log_level="warning")
    server = uvicorn.Server(config)
    server_thread = threading.Thread(target=server.run, daemon=True)
    server_thread.start()

    # Wait for server ready
    backend_url = "http://127.0.0.1:8125"
    ready = False
    for _ in range(50):
        try:
            if httpx.get(f"{backend_url}/status", timeout=1).status_code == 200:
                ready = True
                break
        except Exception:
            time.sleep(0.1)
    assert ready, "Backend failed to start"

    # 2. Start dashboard server pointing to backend
    import subprocess
    dash_proc = subprocess.Popen(
        [sys.executable, str(ROOT / "dashboard" / "app.py")],
        cwd=ROOT,
        env={**os.environ, "PORT": "8075", "BACKEND_URL": backend_url},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    dash_url = "http://127.0.0.1:8075"
    dash_ready = False
    for _ in range(80):
        try:
            if httpx.get(dash_url, timeout=1).status_code == 200:
                dash_ready = True
                break
        except Exception:
            time.sleep(0.2)
    assert dash_ready, "Dashboard failed to start"

    # 3. Setup mock Telegram transport to capture real requests
    telegram_messages = []
    telegram_edits = []
    callback_answers = []

    def telegram_handler(req):
        method = req.url.path.rsplit("/", 1)[-1]
        body = json.loads(req.content)
        if method == "sendMessage":
            telegram_messages.append(body)
            return httpx.Response(200, json={"ok": True, "result": {"message_id": 999}})
        elif method == "editMessageText":
            telegram_edits.append(body)
            return httpx.Response(200, json={"ok": True, "result": {"message_id": 999}})
        elif method == "answerCallbackQuery":
            callback_answers.append(body)
            return httpx.Response(200, json={"ok": True, "result": True})
        return httpx.Response(200, json={"ok": True, "result": True})

    bot = RestTelegramBot(
        bot_token="live-bot-token-sample",
        chat_id="123456",
        backend_url=backend_url,
        approval_token=approval_token,
        allowed_user_ids=[789],
        client=httpx.Client(transport=httpx.MockTransport(telegram_handler)),
        api_client=httpx.Client(timeout=10),
        offset_path=tmp_path / "offset.txt",
    )

    # 4. Bot polls backend: detects incident and sends notification
    bot.poll_api()
    assert len(telegram_messages) == 1
    msg1 = telegram_messages[0]
    print("\n" + "=" * 60)
    print("STEP 4: TELEGRAM MESSAGE (Awaiting Approval):")
    print("=" * 60)
    print(msg1["text"])
    print(f"Buttons: {msg1.get('reply_markup')}")
    print("=" * 60)

    assert "Awaiting approval." in msg1["text"]
    assert "reply_markup" in msg1

    # 5. Screenshot 1: Dashboard showing awaiting approval
    shot1_path = SHOTS_DIR / "live_telegram_1_awaiting_approval_simulated.png"
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        pg = b.new_page(viewport={"width": 1400, "height": 950})
        pg.goto(dash_url, wait_until="load", timeout=30000)
        pg.wait_for_timeout(3000)
        # Ensure token is never visible
        token_val = pg.locator("#token").input_value() if pg.locator("#token").count() else ""
        assert not token_val, "Token must not be visible"
        pg.screenshot(path=shot1_path, full_page=True)
        b.close()
    assert shot1_path.exists()
    print(f"Saved Screenshot 1: {shot1_path}")

    # 6. User taps Approve in Telegram: handle callback query
    query = {
        "id": "cb-live-tap-1",
        "from": {"id": 789, "username": "sanskar"},
        "message": {"chat": {"id": 123456}},
        "data": f"a:{initial_incident['id']}",
    }
    result = bot._handle_callback(query)
    print("\n" + "=" * 60)
    print("STEP 4: APPROVAL 200 RESPONSE:")
    print("=" * 60)
    print(f"Callback result: {result}")
    print(f"Answer callback query: {callback_answers[-1]}")
    print("=" * 60)

    assert result["result"] == "done"
    assert callback_answers[-1]["text"] == "done"

    # 7. Bot polls backend after recovery
    bot.poll_api()
    assert len(telegram_edits) == 1
    edit_msg = telegram_edits[0]
    print("\n" + "=" * 60)
    print("STEP 4: INCIDENT REACHING VERIFIED HEALTHY:")
    print("=" * 60)
    print(edit_msg["text"])
    print(f"Buttons after recovery: {edit_msg.get('reply_markup')}")
    print("=" * 60)

    assert "Approved by telegram:sanskar." in edit_msg["text"]
    assert "Verified healthy" in edit_msg["text"]
    assert edit_msg["reply_markup"] == {"inline_keyboard": []}

    # 8. Screenshot 2: Dashboard showing verified healthy status
    shot2_path = SHOTS_DIR / "live_telegram_2_verified_healthy_simulated.png"
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        pg = b.new_page(viewport={"width": 1400, "height": 950})
        pg.goto(dash_url, wait_until="load", timeout=30000)
        pg.wait_for_timeout(3000)
        token_val = pg.locator("#token").input_value() if pg.locator("#token").count() else ""
        assert not token_val, "Token must not be visible"
        pg.screenshot(path=shot2_path, full_page=True)
        b.close()
    assert shot2_path.exists()
    print(f"Saved Screenshot 2: {shot2_path}")

    server.should_exit = True
    dash_proc.kill()
