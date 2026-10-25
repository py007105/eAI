"""investigate.py: each read-only evidence tool, the repeat-call guard, and retrieval over verified incidents and a KB file."""
import json
import time

import numpy as np
import pandas as pd

from engine import investigate
from engine.investigate import Investigator, remember_verified


class State:
    def __init__(self, running=True, oom=False):
        self.running, self.status, self.image_tag, self.exit_code, self.oom_killed = running, "running" if running else "exited", "v1", 0, oom


class DV:
    def __init__(self):
        self.events = [{"t": time.time() - 30, "service": "orders", "kind": "deploy", "detail": "v1 -> v3-bad"}]

    def state(self):
        return {"orders": State(), "payments": State(running=False, oom=True)}

    def logs(self, service, tail):
        return [json.dumps({"level": "ERROR", "msg": "payment call failed"}), json.dumps({"level": "INFO", "msg": "ok"}),
                json.dumps({"level": "ERROR", "msg": "payment call failed"}), "not json at all",
                json.dumps({"level": "CRITICAL", "msg": "db locked"})]


def inv():
    return Investigator(prom=None, dockerview=DV())


def test_metrics_summary_and_repeat_guard():
    i = inv()
    ev = i.metrics("orders", {"lat_ratio": 2.5, "error_ratio": np.nan, "up_frac": 1.0})
    assert ev.id == "ev1" and "lat_ratio=2.5" in ev.summary and "error_ratio" not in ev.summary
    assert ev.data["error_ratio"] is None
    assert i.metrics("orders", {}) is None and len(i.items) == 1          # same tool + arguments: not run twice
    assert "no data observed" in i.metrics("web", {}).summary


def test_container_and_logs():
    i = inv()
    assert "oom_killed=True" in i.container("payments").summary
    assert "no container" in i.container("web").summary
    ev = i.error_logs("orders")
    assert ev.data["count"] == 3 and ev.data["top"][0] == ("payment call failed", 2)


def test_deploy_history_and_dependency_failures():
    i = inv()
    assert "deploy v1 -> v3-bad" in i.deploy_history("orders").summary
    assert "no deploy/restart seen" in i.deploy_history("web").summary
    ev = i.dependency_failures({("orders", "payments"): 2.0, ("web", "orders"): 0.01})
    assert ev.data == {"orders->payments": 2.0}                           # below 0.05/s is noise


def test_forecast_on_a_steady_leak():
    t = np.arange(0, 120, 2.0)
    df = pd.DataFrame({"mem_bytes": 50e6 + t * 1e6, "mem_limit_bytes": 256e6 * np.ones_like(t),
                       "scratch_bytes": np.zeros_like(t)}, index=t)
    out = inv().forecast("orders", df)
    assert len(out) == 1 and out[0].data["resource"] == "memory" and "exhaustion in" in out[0].summary


def test_similar_incidents_from_store_and_kb(tmp_path, monkeypatch):
    monkeypatch.setattr(investigate, "INCIDENT_STORE", tmp_path / "verified.jsonl")
    kb = tmp_path / "kb.csv"
    kb.write_text("fault_type,name,description,symptoms,reviewed_by_team,eternalai_action\n"
                  "memory_leak,Memory leak,memory grows until the limit,memory rising,no,recreate_container\n", encoding="utf-8")
    monkeypatch.setattr(investigate, "KNOWLEDGE_CSV", kb)
    assert "no past" not in inv().similar_incidents("memory_leak").summary
    remember_verified("memory_leak", "orders", "orders memory leak fixed by recreate", "recreate_container")
    ev = inv().similar_incidents("memory_leak")
    sources = {m["source"] for m in ev.data["matches"]}
    assert "verified_incident" in sources and "knowledge_base_UNREVIEWED" in sources


def test_similar_incidents_with_nothing_available(tmp_path, monkeypatch):
    monkeypatch.setattr(investigate, "INCIDENT_STORE", tmp_path / "none.jsonl")
    monkeypatch.setattr(investigate, "KNOWLEDGE_CSV", tmp_path / "none.csv")
    assert "no past incidents" in inv().similar_incidents("disk_fill").summary
