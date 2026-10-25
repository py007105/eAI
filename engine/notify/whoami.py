"""Print chat id, user id and username from recent Telegram updates."""
from __future__ import annotations

import logging
import os
import sys

import httpx

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


def get_recent_identities(token: str, client: httpx.Client | None = None) -> list[dict]:
    if not token:
        return []
    url = f"https://api.telegram.org/bot{token}/getUpdates"
    own_client = client is None
    c = client or httpx.Client(timeout=15)
    try:
        response = c.post(url, json={"timeout": 0}, timeout=15)
        response.raise_for_status()
        data = response.json()
        if not data.get("ok"):
            return []
    except Exception as exc:
        # Never log or print the URL or token
        print(f"Telegram API error: {type(exc).__name__}", file=sys.stderr)
        return []
    finally:
        if own_client:
            c.close()

    identities = []
    seen = set()
    for update in (data.get("result") or []):
        msg = update.get("message") or update.get("edited_message")
        if msg:
            chat_id = (msg.get("chat") or {}).get("id")
            user = msg.get("from") or {}
            user_id = user.get("id")
            username = user.get("username")
        elif "callback_query" in update:
            cb = update["callback_query"]
            chat_id = ((cb.get("message") or {}).get("chat") or {}).get("id")
            user = cb.get("from") or {}
            user_id = user.get("id")
            username = user.get("username")
        else:
            continue

        if chat_id is not None and user_id is not None:
            key = (chat_id, user_id, username)
            if key not in seen:
                seen.add(key)
                identities.append({
                    "chat_id": chat_id,
                    "user_id": user_id,
                    "username": username,
                })
    return identities


def main() -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        print("TELEGRAM_BOT_TOKEN not found in environment or .env", file=sys.stderr)
        sys.exit(1)

    identities = get_recent_identities(token)
    if not identities:
        print("No recent messages found. Send a message to the bot first.")
        return

    for ident in identities:
        print(f"chat id: {ident['chat_id']}, user id: {ident['user_id']}, username: {ident['username']}")


if __name__ == "__main__":
    main()
