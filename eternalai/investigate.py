"""Tool-using evidence collector. Each tool returns a typed Evidence item with a stable id.

Tools are read-only. A repeat-call guard stops the same tool+arguments from running twice in one
investigation (the pattern is borrowed from HolmesGPT's safeguards, re-implemented here).
Past-incident and runbook retrieval use TF-IDF over reviewed text; unreviewed knowledge is marked.
"""
from __future__ import annotations

import csv
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from . import config
from .forecast import forecast_exhaustion

# Derived from the training workbook, so it is not committed; set EAI_KNOWLEDGE_CSV (e.g. to a bind-mounted file) to use it.
# The knowledge base built by scripts/build_kb.py (data/kb, committed; Package C). EAI_KNOWLEDGE_CSV still overrides it.
KNOWLEDGE_CSV = Path(os.getenv("EAI_KNOWLEDGE_CSV") or
                     Path(__file__).resolve().parents[1] / "data" / "kb" / "knowledge_base.csv")
INCIDENT_STORE = Path("runtime/incidents_verified.jsonl")


@dataclass
class Evidence:
    id: str
    tool: str
    service: str | None
    summary: str
    data: dict = field(default_factory=dict)


class Investigator:
    def __init__(self, prom, dockerview):
        self.prom, self.dv = prom, dockerview
        self._seen: set[str] = set()
        self._n = 0
        self.items: list[Evidence] = []

    def _add(self, tool, service, summary, data=None) -> Evidence:
        self._n += 1
        ev = Evidence(f"ev{self._n}", tool, service, summary, data or {})
        self.items.append(ev)
        return ev

    def _once(self, key):
        if key in self._seen:
            return False
        self._seen.add(key)
        return True

    # ------------------------------------------------------------------ tools
    def metrics(self, service, feats: dict):
        if not self._once(f"metrics:{service}"):
            return None
        keys = ("lat_ratio", "error_ratio", "cpu_per_req_ratio", "mem_share", "mem_rel_growth", "mem_slope_share_per_min",
                "up_frac", "dep_fail_rate", "error_log_rate", "deploys_3m", "restarts_in_window")
        d = {k: (None if not np.isfinite(feats.get(k, np.nan)) else round(float(feats[k]), 4)) for k in keys}
        shown = ", ".join(f"{k}={v}" for k, v in d.items() if v is not None)
        return self._add("metrics", service, f"{service} window metrics: {shown or 'no data observed'}", d)

    def container(self, service):
        if not self._once(f"container:{service}"):
            return None
        st = self.dv.state().get(service)
        if st is None:
            return self._add("container", service, f"{service}: no container found")
        return self._add("container", service,
                         f"{service} container {st.status}, image tag {st.image_tag}, exit_code={st.exit_code}, "
                         f"oom_killed={st.oom_killed}",
                         {"running": st.running, "oom_killed": st.oom_killed, "exit_code": st.exit_code,
                          "image_tag": st.image_tag})

    def error_logs(self, service, tail=40):
        if not self._once(f"logs:{service}"):
            return None
        errs = []
        for line in self.dv.logs(service, tail):
            try:
                rec = json.loads(line)
                if rec.get("level") in ("ERROR", "CRITICAL"):
                    errs.append(rec["msg"])
            except ValueError:
                continue
        top = {}
        for m in errs:
            top[m] = top.get(m, 0) + 1
        common = sorted(top.items(), key=lambda kv: -kv[1])[:3]
        return self._add("error_logs", service, f"{service}: {len(errs)} error log lines in last {tail}; "
                         f"top: {common or 'none'}", {"count": len(errs), "top": common})

    def deploy_history(self, service, window_s=600):
        if not self._once(f"deploys:{service}"):
            return None
        now = time.time()
        ev = [e for e in self.dv.events if e["service"] == service and now - e["t"] < window_s]
        txt = "; ".join(f"{e['kind']} {e['detail']} {now - e['t']:.0f}s ago" for e in ev) or "no deploy/restart seen"
        return self._add("deploy_history", service, f"{service} recent changes: {txt}", {"events": ev})

    def dependency_failures(self, depfail: dict):
        if not self._once("depfail"):
            return None
        hot = {f"{a}->{b}": round(v, 3) for (a, b), v in depfail.items() if v and v > 0.05}
        return self._add("dependency_failures", None,
                         f"failing calls (per second): {hot}" if hot else "no failing dependency calls observed", hot)

    def forecast(self, service, df, scratch_limit=config.SCRATCH_LIMIT_BYTES):
        if not self._once(f"forecast:{service}"):
            return []
        out = []
        for name, col, limit in (("memory", "mem_bytes", df["mem_limit_bytes"].dropna().iloc[-1]
                                  if df["mem_limit_bytes"].notna().any() else float("nan")),
                                 ("disk", "scratch_bytes", scratch_limit)):
            f = forecast_exhaustion(df[col], limit)
            if f:
                out.append(self._add("forecast", service,
                                     f"{service} {name} rising {f['slope_per_min'] / 1e6:.1f} MB/min, "
                                     f"{f['share_of_limit_now'] * 100:.0f}% of limit; exhaustion in "
                                     f"{f['eta_earliest_s']:.0f}-{f['eta_latest_s']:.0f}s", {"resource": name, **f}))
        return out

    def similar_incidents(self, cause: str, k=2):
        """Retrieve past VERIFIED incidents and knowledge-base entries about this cause (TF-IDF over text)."""
        if not self._once(f"similar:{cause}"):
            return None
        from sklearn.feature_extraction.text import TfidfVectorizer
        docs, meta = [], []
        if INCIDENT_STORE.exists():
            for line in INCIDENT_STORE.read_text().splitlines()[-200:]:
                r = json.loads(line)
                docs.append(f"{r['cause']} {r['service']} {r['summary']}")
                meta.append(("verified_incident", r["summary"], r["runbook_id"]))
        if KNOWLEDGE_CSV.exists():
            with KNOWLEDGE_CSV.open(encoding="utf-8") as f:
                for r in csv.DictReader(f):
                    docs.append(f"{r['fault_type']} {r['name']} {r['description']} {r['symptoms']}")
                    meta.append(("knowledge_base_UNREVIEWED" if r["reviewed_by_team"] != "yes" else "knowledge_base",
                                 r["name"] + ": " + r["description"], r["eternalai_action"]))
        if not docs:
            return self._add("similar_incidents", None, "no past incidents or knowledge documents available")
        v = TfidfVectorizer().fit(docs + [cause.replace("_", " ")])
        sims = (v.transform(docs) @ v.transform([cause.replace("_", " ")]).T).toarray().ravel()
        top = [meta[i] for i in np.argsort(-sims)[:k] if sims[i] > 0]
        return self._add("similar_incidents", None,
                         "; ".join(f"[{t}] {txt[:110]}" for t, txt, _ in top) or "no similar documents",
                         {"matches": [{"source": t, "text": txt, "action": a} for t, txt, a in top]})


def remember_verified(cause: str, service: str, summary: str, runbook_id: str):
    """Persist a recovered incident so future retrievals can use it (verified = checkout recovered)."""
    INCIDENT_STORE.parent.mkdir(exist_ok=True)
    with INCIDENT_STORE.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"cause": cause, "service": service, "summary": summary, "runbook_id": runbook_id}) + "\n")
