"""The token the evaluator wants on POST /runs (starting a run injects a real fault, so it is token-protected).

The evaluator holds the brain's approval token (docker-compose.yml, evaluator.environment). Harness scripts send it from
EAI_EVALUATOR_TOKEN, or else ETERNALAI_APPROVAL_TOKEN, taken from the environment. The value is never printed.
"""
from __future__ import annotations

import os
import sys

PLACEHOLDERS = {"", "change-me"}


def evaluator_token() -> str:
    tok = (os.getenv("EAI_EVALUATOR_TOKEN") or os.getenv("ETERNALAI_APPROVAL_TOKEN") or "").strip()
    if tok in PLACEHOLDERS:
        sys.exit("starting an evaluator run needs the approval token: set EAI_EVALUATOR_TOKEN (or ETERNALAI_APPROVAL_TOKEN) "
                 "in this shell to the value the stack was started with")
    return tok


def evaluator_headers() -> dict:
    return {"X-Approval-Token": evaluator_token()}


def check_started(r, what: str = "evaluator run"):
    """Stop with a clear message (never the token) when the evaluator refuses the token."""
    if r.status_code in (403, 503):
        sys.exit(f"{what}: the evaluator refused the token (HTTP {r.status_code}); "
                 "use the token the stack was started with")
    return r
