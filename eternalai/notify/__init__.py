"""Notification interface and environment-based Telegram selection."""
from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from typing import Protocol

from .telegram import TelegramNotifier


class Notifier(Protocol):
    def incident_changed(self, incident: dict) -> None: ...
    def start(self) -> None: ...
    def stop(self) -> None: ...


class NullNotifier:
    def __init__(self, reason: str = "Telegram is not configured"):
        self.reason = reason

    def incident_changed(self, incident: dict) -> None:
        pass

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass


def make_notifier(approve: Callable[[str, str], object], reject: Callable[[str, str], object],
                  approver_for: Callable[[int], str | None], env: Mapping[str, str] = os.environ, *,
                  is_pending: Callable[[str], bool] | None = None,
                  kill_switch_off: Callable[[], bool] | None = None,
                  show_probability: bool = False) -> Notifier:
    """Create a notifier without making a request or starting a thread."""
    token = (env.get("TELEGRAM_BOT_TOKEN") or "").strip()
    chat_id = (env.get("TELEGRAM_CHAT_ID") or "").strip()
    if not token or not chat_id:
        return NullNotifier()
    try:
        chat_number = int(chat_id)
    except ValueError:
        return NullNotifier("TELEGRAM_CHAT_ID is not a number")
    return TelegramNotifier(token, chat_number, approve=approve, reject=reject,
                            approver_for=approver_for, is_pending=is_pending,
                            kill_switch_off=kill_switch_off, show_probability=show_probability)


__all__ = ["Notifier", "NullNotifier", "TelegramNotifier", "make_notifier"]
