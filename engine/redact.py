"""Remove secrets and personal data from text before it leaves the machine (LLM prompt, notifications). Plan §9.6, §14.

Replaced, in this order:
  the exact values of the secrets this process knows (approval token, chaos token, API and bot tokens);
  bearer tokens; credentials in URLs (user:password@host); "key=value" / "key": "value" pairs whose key names a secret;
  JWTs, well-known key formats (Google, AWS, GitHub, Slack, Telegram bot);
  e-mail addresses, IPv4 addresses, phone numbers written with a leading +, payment-card numbers (Luhn-checked);
  long hex or base64-like strings (>= 32 characters), which are usually keys or session ids.
The goal is to fail safe: a redacted container id is an acceptable loss, a leaked token is not.
"""
from __future__ import annotations

import os
import re

SECRET_ENV = ("ETERNALAI_APPROVAL_TOKEN", "CHAOS_TOKEN", "GEMINI_API_KEY", "GROQ_API_KEY", "TELEGRAM_BOT_TOKEN",
              "SLACK_BOT_TOKEN", "SLACK_SIGNING_SECRET", "PAGERDUTY_ROUTING_KEY")
PLACEHOLDERS = {"", "change-me", "evaluator-only"}

SECRET_KEY = r"(?:pass(?:word|wd)?|pwd|secret|token|api[_-]?key|apikey|access[_-]?key|private[_-]?key|auth(?:orization)?|" \
             r"session(?:id)?|cookie|credential|signature)"
_PATTERNS = [
    (re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{8,}"), "Bearer [REDACTED]"),       # before key=value, which would stop at "Bearer"
    (re.compile(r"(?i)\b([a-z][a-z0-9+.-]*://)([^/\s:@]+):([^/\s@]+)@"), r"\1[REDACTED]@"),
    (re.compile(r"(?i)(\"?\b[\w.-]*" + SECRET_KEY + r"[\w.-]*\"?\s*[:=]\s*\"?)([^\s\",;&}]+)"), r"\1[REDACTED]"),
    (re.compile(r"\beyJ[\w-]{5,}\.[\w-]{5,}\.[\w-]{5,}"), "[REDACTED]"),
    (re.compile(r"\bAIza[0-9A-Za-z_-]{30,}"), "[REDACTED]"),
    (re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"), "[REDACTED]"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}"), "[REDACTED]"),
    (re.compile(r"\bxox[abposr]-[A-Za-z0-9-]{10,}"), "[REDACTED]"),
    (re.compile(r"\b\d{6,12}:[A-Za-z0-9_-]{30,}"), "[REDACTED]"),                       # Telegram bot token
    (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"), "[EMAIL]"),
    (re.compile(r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b"), "[IP]"),
    (re.compile(r"\+\d[\d ()-]{7,}\d"), "[PHONE]"),
]
_CARD = re.compile(r"\b(?:\d[ -]?){12,18}\d\b")
_LONG = re.compile(r"\b(?=[A-Za-z0-9+/_-]*\d)(?=[A-Za-z0-9+/_-]*[A-Za-z])[A-Za-z0-9+/_-]{32,}={0,2}")


def _luhn(digits: str) -> bool:
    total, alt = 0, False
    for ch in reversed(digits):
        d = int(ch)
        if alt:
            d = d * 2 - 9 if d > 4 else d * 2
        total, alt = total + d, not alt
    return total % 10 == 0


def _card(m: re.Match) -> str:
    digits = re.sub(r"\D", "", m.group(0))
    return "[CARD]" if 13 <= len(digits) <= 19 and _luhn(digits) else m.group(0)


def known_secrets() -> list[str]:
    vals = [os.getenv(k, "") for k in SECRET_ENV]
    return sorted({v for v in vals if v not in PLACEHOLDERS and len(v) >= 6}, key=len, reverse=True)


def redact(text: str) -> str:
    if not text:
        return text
    out = str(text)
    for secret in known_secrets():
        out = out.replace(secret, "[REDACTED]")
    for pat, repl in _PATTERNS:
        out = pat.sub(repl, out)
    out = _CARD.sub(_card, out)
    return _LONG.sub("[REDACTED]", out)
