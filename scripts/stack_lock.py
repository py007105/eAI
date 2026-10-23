"""The shared Docker lock (D:\\eAI\\STACK_LOCK.md; protocol in docs/COORDINATION.md section 5).

The file starts with the agreed Docker schedule; its LAST line is the lock: `FREE | ...` or `HELD by <who> | ...`.
These helpers change only that last line, so the schedule above it is kept.

Parent mode: a long sequence (scripts/run_v3_sequence.py) takes the lock ONCE and holds it across all its steps. It starts
its child scripts with EAI_STACK_LOCK_PARENT=<who>; in a child, take() only checks that the lock is still held by that
owner and release() does nothing, so the lock never reads FREE between steps. The parent releases it in a `finally`.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

LOCK = Path(r"D:\eAI\STACK_LOCK.md")
IST = timezone(timedelta(hours=5, minutes=30))
PARENT_ENV = "EAI_STACK_LOCK_PARENT"


def ist() -> str:
    return datetime.now(IST).strftime("%Y-%m-%d %H:%M IST")


def _split(path: Path) -> tuple[list[str], str]:
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    while lines and not lines[-1].strip():
        lines.pop()
    if lines and lines[-1].startswith(("FREE", "HELD")):
        return lines[:-1], lines[-1]
    return lines, "FREE"


def state(path: Path = LOCK) -> str:
    return _split(path)[1]


def _write(path: Path, head: list[str], last: str):
    path.write_text("\n".join(head + [last]) + "\n", encoding="utf-8")


def _parent(who: str) -> bool:
    return os.environ.get(PARENT_ENV) == who


def take(who: str, what: str, images: str, path: Path = LOCK):
    head, cur = _split(path)
    if _parent(who):
        if not cur.startswith(f"HELD by {who}"):
            raise SystemExit(f"parent sequence should hold the Docker lock, but it reads: {cur}")
        return
    if cur.startswith("HELD") and not cur.startswith(f"HELD by {who}"):
        raise SystemExit(f"Docker lock is held by another session: {cur}")
    _write(path, head, f"HELD by {who} | {what} | since {ist()} | images built from {images}")


def release(who: str, images: str, path: Path = LOCK):
    if _parent(who):
        return          # the parent sequence releases the lock when it ends
    head, _ = _split(path)
    _write(path, head, f"FREE | last: {who} | images now built from {images} | {ist()}")
