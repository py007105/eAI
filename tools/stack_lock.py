"""The shared Docker lock (D:\\eAI\\STACK_LOCK.md + D:\\eAI\\STACK_LOCK.owner; protocol in docs/COORDINATION.md section 5).

OWNERSHIP is the owner file D:\\eAI\\STACK_LOCK.owner, created ATOMICALLY with O_CREAT|O_EXCL: of two processes trying at the
same moment exactly one succeeds. It holds a random token. Seeing "FREE" in the schedule file is NOT ownership.
The last line of STACK_LOCK.md is the human-readable display (`FREE | ...` / `HELD by <who> | ...`); the schedule above it is
kept. take() refuses if the owner file exists OR the display says HELD (a holder using the older display-only mechanism).
release() removes the lock only if the owner file carries the caller's token: nobody can release someone else's lock.
A crashed owner leaves its owner file behind; it is never stolen automatically (check `pid` in it, then remove by hand).

Parent mode: a sequence (tools/run_v3_sequence.py) takes the lock once and passes EAI_STACK_LOCK_PARENT=<who> and
EAI_STACK_LOCK_TOKEN=<token> to its children; in a child, take() only verifies that the owner file still carries that token
and release() does nothing, so the lock is held across the whole sequence. Codex uses this same module.
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

LOCK = Path(r"D:\eAI\STACK_LOCK.md")
IST = timezone(timedelta(hours=5, minutes=30))
PARENT_ENV, TOKEN_ENV = "EAI_STACK_LOCK_PARENT", "EAI_STACK_LOCK_TOKEN"
_held: dict[str, str] = {}          # lock path -> token taken by this process


def ist() -> str:
    return datetime.now(IST).strftime("%Y-%m-%d %H:%M IST")


def owner_path(path: Path) -> Path:
    return path.with_suffix(".owner")


def _split(path: Path) -> tuple[list[str], str]:
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    while lines and not lines[-1].strip():
        lines.pop()
    if lines and lines[-1].startswith(("FREE", "HELD")):
        return lines[:-1], lines[-1]
    return lines, "FREE"


def state(path: Path = LOCK) -> str:
    return _split(path)[1]


def owner(path: Path = LOCK) -> dict | None:
    try:
        return json.loads(owner_path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def is_free(path: Path = LOCK) -> bool:
    return owner(path) is None and not owner_path(path).exists() and state(path).startswith("FREE")


def _write(path: Path, head: list[str], last: str):
    path.write_text("\n".join(head + [last]) + "\n", encoding="utf-8")


def take(who: str, what: str, images: str, path: Path = LOCK) -> str:
    if os.environ.get(PARENT_ENV) == who:
        o = owner(path)
        if not o or o.get("token") != os.environ.get(TOKEN_ENV):
            raise SystemExit(f"parent sequence should own the Docker lock, but the owner is: {o}")
        return o["token"]
    head, cur = _split(path)
    if cur.startswith("HELD"):
        raise SystemExit(f"Docker lock is held (display): {cur}")
    token = uuid.uuid4().hex
    try:
        fd = os.open(owner_path(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise SystemExit(f"Docker lock is owned by: {owner(path)}") from None
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump({"who": who, "what": what, "token": token, "pid": os.getpid(), "since": ist()}, f)
    _held[str(path)] = token
    _write(path, head, f"HELD by {who} | {what} | since {ist()} | images built from {images}")
    return token


def release(who: str, images: str, path: Path = LOCK, token: str | None = None):
    if os.environ.get(PARENT_ENV) == who:
        return          # the parent sequence releases the lock when it ends
    token = token or _held.get(str(path))
    o = owner(path)
    if not o or not token or o.get("token") != token:
        raise SystemExit(f"refusing to release a Docker lock this process does not own (owner: {o})")
    head, _ = _split(path)
    _write(path, head, f"FREE | last: {who} | images now built from {images} | {ist()}")
    owner_path(path).unlink()
    _held.pop(str(path), None)
