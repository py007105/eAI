"""Learn store (plan §9.7, §16 task 8, light version): every closed incident, its actions, its verified outcome and any human
feedback, in SQLite.

    ETERNALAI_DB_URL=sqlite:///runtime/eternalai.db   (default; inside the brain container runtime/ is the eternalai-runtime volume)

Only SQLite is implemented. The schema uses plain SQL types and no SQLite-only features so it can move to Postgres; a
Postgres URL is refused with a clear message instead of being half-supported. Writes happen outside the engine lock.
Rows are append/upsert only; nothing here deletes data.
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from pathlib import Path

SCHEMA = [
    """CREATE TABLE IF NOT EXISTS incidents (
        id TEXT PRIMARY KEY, opened_t REAL, closed_t REAL, kind TEXT, status TEXT, services TEXT, root TEXT,
        likely_cause TEXT, confidence REAL, abstained INTEGER, diagnosis TEXT, root_features TEXT, report_summary TEXT,
        stored_t REAL)""",
    """CREATE TABLE IF NOT EXISTS actions (
        incident_id TEXT, seq INTEGER, t REAL, runbook_id TEXT, service TEXT, verdict TEXT, risk TEXT, reason TEXT,
        executed INTEGER, approved_by TEXT, result TEXT, PRIMARY KEY (incident_id, seq))""",
    """CREATE TABLE IF NOT EXISTS outcomes (
        incident_id TEXT PRIMARY KEY, outcome TEXT, success_rate REAL, probes INTEGER, checkout_before REAL,
        checkout_after REAL, time_to_verified_s REAL)""",
    """CREATE TABLE IF NOT EXISTS feedback (
        id INTEGER PRIMARY KEY AUTOINCREMENT, incident_id TEXT, t REAL, approver TEXT, confirmed INTEGER,
        correct_fault TEXT, note TEXT)""",
]


class StoreError(ValueError):
    pass


def db_path(url: str | None = None) -> Path:
    url = (url or os.getenv("ETERNALAI_DB_URL") or os.getenv("DB_URL") or "sqlite:///runtime/eternalai.db").strip()
    if not url.startswith("sqlite:///"):
        raise StoreError(f"only sqlite:/// URLs are implemented (got scheme {url.split(':', 1)[0]!r}); Postgres is roadmap")
    return Path(url[len("sqlite:///"):])


class LearnStore:
    def __init__(self, url: str | None = None):
        self.path = db_path(url)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        with self._conn() as c:
            for stmt in SCHEMA:
                c.execute(stmt)

    def _conn(self):
        c = sqlite3.connect(self.path, timeout=10)
        c.row_factory = sqlite3.Row
        return c

    def record_incident(self, inc: dict):
        """Upsert one closed incident (Incident.public() plus root_features) with its actions and outcome."""
        diag = inc.get("diagnosis") or {}
        root = diag.get("root") or ((inc.get("ranking") or [{}])[0].get("service"))
        ver, before, after = inc.get("verification") or {}, inc.get("before") or {}, inc.get("after") or {}
        acts = inc.get("actions") or []
        executed_t = next((a.get("executed_t") for a in acts if a.get("executed")), None)
        with self._lock, self._conn() as c:
            c.execute("INSERT OR REPLACE INTO incidents VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                      (inc["id"], inc.get("opened_t"), inc.get("closed_t"), inc.get("kind"), inc.get("status"),
                       json.dumps(inc.get("services") or []), root, inc.get("likely_cause"), inc.get("confidence"),
                       int(bool(inc.get("abstained"))), json.dumps(diag, default=str),
                       json.dumps(inc.get("root_features") or {}, default=str),
                       (inc.get("report") or {}).get("summary"), time.time()))
            for i, a in enumerate(acts):
                c.execute("INSERT OR REPLACE INTO actions VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                          (inc["id"], i, a.get("t"), a.get("runbook_id"), a.get("service"), a.get("verdict"), a.get("risk"),
                           a.get("reason"), int(bool(a.get("executed"))), a.get("approved_by"),
                           json.dumps(a.get("result"), default=str)))
            if ver:
                c.execute("INSERT OR REPLACE INTO outcomes VALUES (?,?,?,?,?,?,?)",
                          (inc["id"], ver.get("outcome"), ver.get("success_rate"), ver.get("probes"),
                           before.get("checkout_success"), after.get("checkout_success"),
                           (ver["t"] - executed_t) if executed_t and ver.get("t") else None))

    def add_feedback(self, incident_id: str, approver: str, confirmed: bool, correct_fault: str | None, note: str) -> int:
        with self._lock, self._conn() as c:
            if not c.execute("SELECT 1 FROM incidents WHERE id=?", (incident_id,)).fetchone():
                raise StoreError(f"no closed incident {incident_id!r} in the learn store")
            cur = c.execute("INSERT INTO feedback (incident_id, t, approver, confirmed, correct_fault, note) VALUES (?,?,?,?,?,?)",
                            (incident_id, time.time(), approver, int(confirmed), correct_fault, note))
            return int(cur.lastrowid)

    def incident(self, incident_id: str) -> dict | None:
        with self._conn() as c:
            row = c.execute("SELECT * FROM incidents WHERE id=?", (incident_id,)).fetchone()
            if not row:
                return None
            out = dict(row)
            out["actions"] = [dict(r) for r in c.execute("SELECT * FROM actions WHERE incident_id=? ORDER BY seq", (incident_id,))]
            o = c.execute("SELECT * FROM outcomes WHERE incident_id=?", (incident_id,)).fetchone()
            out["outcome"] = dict(o) if o else None
            out["feedback"] = [dict(r) for r in c.execute("SELECT * FROM feedback WHERE incident_id=? ORDER BY id", (incident_id,))]
            return out

    def counts(self) -> dict:
        with self._conn() as c:
            return {t: c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ("incidents", "actions", "outcomes", "feedback")}

    def training_rows(self) -> tuple[list[dict], list[dict]]:
        """Dataset-A-style rows (root features + label) and dataset-C-style rows (fault, fix, outcome) for retraining and fix
        ranking. The label is the human-corrected fault if any feedback corrected it, else the diagnosed fault when a human
        confirmed it; unconfirmed incidents get label None (never used as ground truth without a human)."""
        a_rows, c_rows = [], []
        with self._conn() as c:
            for inc in c.execute("SELECT * FROM incidents ORDER BY opened_t"):
                fb = c.execute("SELECT * FROM feedback WHERE incident_id=? ORDER BY id DESC", (inc["id"],)).fetchone()
                label = (fb["correct_fault"] or (inc["likely_cause"] if fb["confirmed"] else None)) if fb else None
                a_rows.append({"incident_id": inc["id"], "root": inc["root"], "label": label, "label_source":
                               ("human" if fb else None), **json.loads(inc["root_features"] or "{}")})
                act = c.execute("SELECT * FROM actions WHERE incident_id=? AND executed=1 ORDER BY seq LIMIT 1", (inc["id"],)).fetchone()
                out = c.execute("SELECT * FROM outcomes WHERE incident_id=?", (inc["id"],)).fetchone()
                if act:
                    c_rows.append({"incident_id": inc["id"], "fault": label or inc["likely_cause"], "fault_source":
                                   "human" if label else "diagnosis", "fix": act["runbook_id"], "service": act["service"],
                                   "outcome": out["outcome"] if out else None,
                                   "success_rate": out["success_rate"] if out else None,
                                   "time_to_verified_s": out["time_to_verified_s"] if out else None})
        return a_rows, c_rows
