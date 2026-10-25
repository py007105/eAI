"""REST-only Telegram notification and approval bot."""
from __future__ import annotations

import logging
import os
import signal
import sys
import threading
from pathlib import Path
from typing import Any

import httpx

from engine.redact import redact

from .format import format_incident
from .telegram import _CALLBACK, TelegramNotifier

LOG = logging.getLogger(__name__)

# httpx/httpcore can include the token-bearing URL or authorization in their INFO/DEBUG logs.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


class RestTelegramBot(TelegramNotifier):
    """Polls backend REST API every 2s and handles Telegram approvals."""

    def __init__(self, bot_token: str, chat_id: str | int,
                 backend_url: str = "http://localhost:8000",
                 approval_token: str = "",
                 allowed_user_ids: int | str | list[int | str] | set[int] | None = None,
                 client: httpx.Client | None = None,
                 api_client: httpx.Client | None = None,
                 offset_path: str | Path = "runtime/telegram_update_id.txt",
                 show_probability: bool = False):
        super().__init__(bot_token, chat_id, client=client, offset_path=offset_path, show_probability=show_probability)
        self.backend_url = backend_url.rstrip("/")
        self.approval_token = approval_token
        self.api_client = api_client or httpx.Client(timeout=10)
        self._own_api_client = api_client is None
        self.active_approvals: set[str] = set()
        self.kill_switch: bool = False

        if isinstance(allowed_user_ids, (int, str)):
            self.allowed_user_ids = {int(x.strip()) for x in str(allowed_user_ids).split(",") if x.strip().isdigit()}
        elif allowed_user_ids is not None:
            self.allowed_user_ids = {int(x) for x in allowed_user_ids}
        else:
            uid_env = os.getenv("TELEGRAM_USER_ID", "").strip()
            if uid_env:
                self.allowed_user_ids = {int(x.strip()) for x in uid_env.split(",") if x.strip().isdigit()}
            else:
                self.allowed_user_ids = set()

    def _is_allowed_user(self, user_id: int | None) -> bool:
        if not isinstance(user_id, int):
            return False
        if not self.allowed_user_ids:
            return False
        return user_id in self.allowed_user_ids

    def _keyboard(self, incident: dict) -> dict | None:
        iid = str(incident.get("id") or "")
        if iid not in self.active_approvals:
            return None
        return TelegramNotifier._keyboard(incident)

    def _visible_state(self, incident: dict) -> tuple:
        base = TelegramNotifier._visible_state(incident)
        iid = str(incident.get("id") or "")
        in_approvals = iid in self.active_approvals
        return base + (in_approvals, self.show_probability)

    def _call_approval_api(self, iid: str, action: str, username: str) -> str:
        url = f"{self.backend_url}/approvals/{iid}/{action}"
        headers = {}
        if self.approval_token:
            headers["X-Approval-Token"] = self.approval_token
        payload = {"approver": f"telegram:{username}"}
        try:
            resp = self.api_client.post(url, json=payload, headers=headers, timeout=10)
            if resp.status_code == 200:
                return "done"
            elif resp.status_code == 409:
                return "already handled/expired"
            elif resp.status_code in (403, 503):
                return "token refused"
            else:
                return f"HTTP {resp.status_code}"
        except Exception as exc:
            LOG.warning("Approval API error: %s", type(exc).__name__)
            return "action failed"

    def _handle_callback(self, query: dict) -> dict:
        callback_id = query.get("id")
        data = query.get("data")
        user = query.get("from") or {}
        user_id = user.get("id")
        username = user.get("username") or str(user_id)
        chat_id = (((query.get("message") or {}).get("chat") or {}).get("id"))
        result = "not authorized"
        iid = None
        action = None

        if str(chat_id) != self.chat_id:
            result = "not authorized"
        elif not self._is_allowed_user(user_id):
            result = "not an approver"
        else:
            match = _CALLBACK.fullmatch(data) if isinstance(data, str) and len(data.encode("utf-8")) <= 64 else None
            if not match:
                result = "invalid button"
            else:
                action, iid = match.groups()
                if self.kill_switch:
                    result = "kill switch is on"
                else:
                    endpoint = "approve" if action == "a" else "reject"
                    result = self._call_approval_api(iid, endpoint, username)

        if callback_id:
            self._request("answerCallbackQuery", {"callback_query_id": callback_id, "text": redact(result)})
        return {"incident_id": iid, "action": action, "result": result}

    def poll_api(self) -> None:
        try:
            r_status = self.api_client.get(f"{self.backend_url}/status", timeout=10)
            r_status.raise_for_status()
            status_data = r_status.json()
            self.kill_switch = bool(status_data.get("kill_switch", False))
            self.show_probability = bool((status_data.get("calibration") or {}).get("show_probability", False))
        except Exception as exc:
            LOG.warning("Backend API status error: %s", type(exc).__name__)
            return

        try:
            r_app = self.api_client.get(f"{self.backend_url}/approvals", timeout=10)
            r_app.raise_for_status()
            approvals_data = r_app.json()
            self.active_approvals = {str(a.get("incident_id") or "") for a in approvals_data if a.get("incident_id")}
        except Exception as exc:
            LOG.warning("Backend API approvals error: %s", type(exc).__name__)
            return

        try:
            r_inc = self.api_client.get(f"{self.backend_url}/incidents", timeout=10)
            r_inc.raise_for_status()
            incidents_data = r_inc.json()
        except Exception as exc:
            LOG.warning("Backend API incidents error: %s", type(exc).__name__)
            return

        for inc in incidents_data:
            iid = str(inc.get("id") or "")
            if not iid:
                continue
            state = self._visible_state(inc)
            if self._visible_states.get(iid) == state:
                continue

            msg_id = self._message_ids.get(iid)
            if msg_id is None:
                new_msg_id = self.send_incident(inc)
                if new_msg_id is not None:
                    self._message_ids[iid] = new_msg_id
                    self._visible_states[iid] = state
            else:
                ok = self.update_incident(msg_id, inc)
                if ok:
                    self._visible_states[iid] = state

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._poll_loop, name="telegram-poll", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)
        if self._own_client:
            self.client.close()
        if self._own_api_client:
            self.api_client.close()

    def run(self) -> None:
        self.start()
        LOG.info("REST Telegram bot started; polling backend %s every 2s", self.backend_url)
        try:
            while not self._stop.is_set():
                self.poll_api()
                self._stop.wait(2.0)
        finally:
            self.stop()
            LOG.info("REST Telegram bot stopped")


def main() -> None:
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not bot_token or not chat_id:
        print("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are required in environment or .env", file=sys.stderr)
        sys.exit(1)

    backend_url = os.getenv("BACKEND_URL", "http://localhost:8000").strip()
    approval_token = os.getenv("ETERNALAI_APPROVAL_TOKEN", "").strip()
    user_id_env = os.getenv("TELEGRAM_USER_ID", "").strip()

    bot = RestTelegramBot(
        bot_token=bot_token,
        chat_id=chat_id,
        backend_url=backend_url,
        approval_token=approval_token,
        allowed_user_ids=user_id_env or None,
    )

    def sig_handler(sig, frame):
        bot.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    try:
        bot.run()
    except KeyboardInterrupt:
        bot.stop()


if __name__ == "__main__":
    main()
