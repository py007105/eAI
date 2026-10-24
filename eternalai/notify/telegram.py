"""Telegram delivery and private-chat approval polling, without a webhook."""
from __future__ import annotations

import logging
import os
import queue
import re
import threading
from copy import deepcopy
from pathlib import Path
from typing import Callable

import httpx

from eternalai.redact import redact

from .format import format_incident


LOG = logging.getLogger(__name__)
_CALLBACK = re.compile(r"([ar]):([A-Za-z0-9_-]{1,62})\Z", re.ASCII)


class TelegramNotifier:
    """Send and edit incident messages; poll callbacks on a daemon thread.

    The callback functions are bound by the engine later. Until all five are
    supplied, button taps are refused rather than treated as authenticated.
    """

    def __init__(self, bot_token: str, chat_id: str | int, client: httpx.Client | None = None, *,
                 approve: Callable[[str, str], object] | None = None,
                 reject: Callable[[str, str], object] | None = None,
                 approver_for: Callable[[int], str | None] | None = None,
                 is_pending: Callable[[str], bool] | None = None,
                 kill_switch_off: Callable[[], bool] | None = None,
                 offset_path: str | Path = "runtime/telegram_update_id.txt",
                 show_probability: bool = False):
        if not bot_token or not str(chat_id):
            raise ValueError("Telegram bot token and chat id are required")
        self._base_url = f"https://api.telegram.org/bot{bot_token}/"
        self.chat_id = str(chat_id)
        # httpx/httpcore can include the token-bearing URL in their own INFO/DEBUG logs.
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)
        self.client = client or httpx.Client(timeout=30)
        self._own_client = client is None
        self.approve, self.reject = approve, reject
        self.approver_for = approver_for
        self.is_pending, self.kill_switch_off = is_pending, kill_switch_off
        self.offset_path = Path(offset_path)
        self.show_probability = show_probability
        self.last_error: str | None = None
        self._last_update_id = self._load_update_id()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._delivery_thread: threading.Thread | None = None
        self._send_queue: queue.Queue[tuple[str, tuple, dict]] = queue.Queue(maxsize=64)
        self._delivery_lock = threading.Lock()
        self._message_ids: dict[str, int] = {}
        self._visible_states: dict[str, tuple] = {}

    def configure_callbacks(self, *, approve: Callable[[str, str], object],
                            reject: Callable[[str, str], object],
                            approver_for: Callable[[int], str | None],
                            is_pending: Callable[[str], bool],
                            kill_switch_off: Callable[[], bool]) -> None:
        self.approve, self.reject = approve, reject
        self.approver_for = approver_for
        self.is_pending, self.kill_switch_off = is_pending, kill_switch_off

    def _load_update_id(self) -> int | None:
        try:
            return int(self.offset_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def _save_update_id(self, update_id: int) -> None:
        self.offset_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.offset_path.with_suffix(self.offset_path.suffix + ".tmp")
        tmp.write_text(str(update_id), encoding="utf-8")
        os.replace(tmp, self.offset_path)
        self._last_update_id = update_id

    def _request(self, method: str, payload: dict, *, timeout: int = 30) -> dict | None:
        # Bot API URLs contain the secret. Never log a URL, payload, or exception message.
        try:
            response = self.client.post(self._base_url + method, json=payload, timeout=timeout)
            response.raise_for_status()
            data = response.json()
            if data.get("ok") is not True:
                self.last_error = "TelegramAPIError"
                LOG.warning("Telegram API error: %s", self.last_error)
                return None
            self.last_error = None
            return data
        except Exception as exc:  # httpx errors include the token-bearing URL
            self.last_error = type(exc).__name__
            LOG.warning("Telegram API error: %s", self.last_error)
            return None

    @staticmethod
    def _keyboard(incident: dict) -> dict | None:
        actions = incident.get("actions") or []
        if not actions or actions[-1].get("verdict") != "needs_approval" or incident.get("status") != "awaiting_approval":
            return None
        iid = str(incident.get("id") or "")
        if not _CALLBACK.fullmatch("a:" + iid) or len(("a:" + iid).encode("utf-8")) > 64:
            return None
        return {"inline_keyboard": [[
            {"text": redact("Approve"), "callback_data": "a:" + iid},
            {"text": redact("Reject"), "callback_data": "r:" + iid},
        ]]}

    def send_incident(self, incident_dict: dict) -> int | None:
        payload = {"chat_id": self.chat_id,
                   "text": format_incident(incident_dict, show_probability=self.show_probability)}
        keyboard = self._keyboard(incident_dict)
        if keyboard:
            payload["reply_markup"] = keyboard
        data = self._request("sendMessage", payload)
        return (data.get("result") or {}).get("message_id") if data else None

    def update_incident(self, message_id: int, incident_dict: dict) -> bool:
        payload = {"chat_id": self.chat_id, "message_id": message_id,
                   "text": format_incident(incident_dict, show_probability=self.show_probability),
                   "reply_markup": self._keyboard(incident_dict) or {"inline_keyboard": []}}
        return self._request("editMessageText", payload) is not None

    @staticmethod
    def _visible_state(incident: dict) -> tuple:
        action = (incident.get("actions") or [{}])[-1]
        verification = incident.get("verification") or {}
        return (incident.get("status"), action.get("verdict"), action.get("approved_by"),
                verification.get("outcome"))

    def incident_changed(self, incident: dict) -> None:
        """Queue one snapshot only when a user-visible state field changes."""
        iid = incident.get("id")
        if not isinstance(iid, str) or not iid:
            return
        state = self._visible_state(incident)
        with self._delivery_lock:
            if self._visible_states.get(iid) == state:
                return
            try:
                self._send_queue.put_nowait((iid, state, deepcopy(incident)))
            except queue.Full as exc:
                self.last_error = type(exc).__name__
                LOG.warning("Telegram delivery error: %s", self.last_error)
                return
            self._visible_states[iid] = state

    def _send_loop(self) -> None:
        while not self._stop.is_set() or not self._send_queue.empty():
            try:
                iid, state, incident = self._send_queue.get(timeout=0.2)
            except queue.Empty:
                continue
            try:
                with self._delivery_lock:
                    message_id = self._message_ids.get(iid)
                if message_id is None:
                    message_id = self.send_incident(incident)
                    ok = message_id is not None
                    if ok:
                        with self._delivery_lock:
                            self._message_ids[iid] = message_id
                else:
                    ok = self.update_incident(message_id, incident)
                if not ok:
                    with self._delivery_lock:
                        if self._visible_states.get(iid) == state:
                            self._visible_states.pop(iid, None)
            except Exception as exc:
                self.last_error = type(exc).__name__
                LOG.warning("Telegram delivery error: %s", self.last_error)
                with self._delivery_lock:
                    if self._visible_states.get(iid) == state:
                        self._visible_states.pop(iid, None)
            finally:
                self._send_queue.task_done()

    def _handle_callback(self, query: dict) -> dict:
        callback_id = query.get("id")
        data = query.get("data")
        user_id = (query.get("from") or {}).get("id")
        chat_id = (((query.get("message") or {}).get("chat") or {}).get("id"))
        result = "not authorized"
        iid = None
        action = None
        if str(chat_id) == self.chat_id and isinstance(user_id, int) and self.approver_for:
            result = "not an approver"
            try:
                approver = self.approver_for(user_id)
            except Exception as exc:
                self.last_error = type(exc).__name__
                LOG.warning("Telegram callback error: %s", self.last_error)
                approver = None
            if approver:
                if isinstance(data, str) and len(data.encode("utf-8")) <= 64:
                    match = _CALLBACK.fullmatch(data)
                else:
                    match = None
                if match:
                    action, iid = match.groups()
                    if not all((self.approve, self.reject, self.is_pending, self.kill_switch_off)):
                        result = "not available"
                    else:
                        try:
                            if not self.kill_switch_off():
                                result = "kill switch is on"
                            elif not self.is_pending(iid):
                                result = "already handled"
                            else:
                                (self.approve if action == "a" else self.reject)(iid, approver)
                                result = "approved" if action == "a" else "rejected"
                        except ValueError:
                            result = "already handled"
                        except Exception as exc:
                            self.last_error = type(exc).__name__
                            LOG.warning("Telegram callback error: %s", self.last_error)
                            result = "action failed"
                else:
                    result = "invalid button"
        if callback_id:
            self._request("answerCallbackQuery", {"callback_query_id": callback_id, "text": redact(result)})
        return {"incident_id": iid, "action": action, "result": result}

    def poll_once(self) -> list[dict]:
        payload = {"timeout": 25, "allowed_updates": ["callback_query"]}
        if self._last_update_id is not None:
            payload["offset"] = self._last_update_id + 1
        data = self._request("getUpdates", payload, timeout=30)
        handled = []
        for update in (data or {}).get("result") or []:
            update_id = update.get("update_id")
            if not isinstance(update_id, int) or (self._last_update_id is not None and update_id <= self._last_update_id):
                continue
            try:
                # Persist first: a restart must not replay an already received tap.
                self._save_update_id(update_id)
            except OSError as exc:
                self.last_error = type(exc).__name__
                LOG.warning("Telegram offset error: %s", self.last_error)
                break
            if "callback_query" in update:
                handled.append(self._handle_callback(update["callback_query"]))
        return handled

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._delivery_thread = threading.Thread(target=self._send_loop, name="telegram-send", daemon=True)
        self._delivery_thread.start()
        self._thread = threading.Thread(target=self._poll_loop, name="telegram-poll", daemon=True)
        self._thread.start()

    def _poll_loop(self) -> None:
        while not self._stop.is_set():
            try:
                self.poll_once()
            except Exception as exc:
                self.last_error = type(exc).__name__
                LOG.warning("Telegram poll error: %s", self.last_error)
            if self.last_error:
                self._stop.wait(1)

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=26)
        if self._delivery_thread and self._delivery_thread.is_alive():
            self._delivery_thread.join(timeout=30)
        if self._own_client:
            self.client.close()
