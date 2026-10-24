"""Package C: knowledge-base loading/validation, outcome-ranked fix choice, engine wiring and GET /kb."""
import shutil
from pathlib import Path

import pandas as pd
import pytest

from eternalai.classify import CAUSE_RUNBOOKS
from eternalai.kb import KBError, load_kb, ranked_fixes, ranked_runbooks
from eternalai.kb.labels import FIX_TO_RUNBOOK, LIVE_TO_PLAN

REAL = Path(__file__).resolve().parents[1] / "data" / "kb"


def tiny_kb(tmp_path, measured=None, prototype=None, options=None):
    d = tmp_path / "kb"
    d.mkdir(parents=True)
    pd.DataFrame([{"fault_type": "memory_leak", "name": "Memory leak", "category": "resource", "description": "grows",
                   "symptoms": "memory rising", "eternalai_action": "restart", "sources": "https://example.org/x",
                   "reviewed_by_team": "no", "source_sheet": "B_knowledge_base"}]).to_csv(d / "knowledge_base.csv", index=False)
    pd.DataFrame(options or [
        {"fault_type": "memory_leak", "rank_prior": 1, "fix_id": "restart_in_place", "fix": "Restart in place", "risk": "low",
         "automation": "automatic", "source_sheet": "B_fix_options"},
        {"fault_type": "memory_leak", "rank_prior": 2, "fix_id": "scale_out", "fix": "Scale out", "risk": "low",
         "automation": "automatic", "source_sheet": "B_fix_options"}]).to_csv(d / "fix_options.csv", index=False)
    pd.DataFrame([{"fix_id": "restart_in_place", "fix": "Restart in place", "what_it_does": "restart"}]).to_csv(
        d / "fix_catalog.csv", index=False)
    pd.DataFrame(prototype or [{"fault_type": "memory_leak", "fix_id": "restart_in_place", "recovered": True, "failed_pct": 2.0,
                                "environment": "prototype"}]).to_csv(d / "outcomes_prototype.csv", index=False)
    pd.DataFrame(measured or [{"live_label": "memory_leak", "fix": "recreate_container", "recovered": True, "failed_request_pct": 6.0,
                               "time_to_verified_recovery_s": 47.0, "source_file": "x", "policy": "p"}]).to_csv(
        d / "outcomes_measured.csv", index=False)
    return d


def test_missing_kb_means_fixed_table(tmp_path):
    assert load_kb(tmp_path / "none") is None
    for label, rbs in CAUSE_RUNBOOKS.items():
        assert ranked_runbooks(None, label) == rbs


def test_validation(tmp_path):
    d = tiny_kb(tmp_path)
    (d / "fix_catalog.csv").unlink()
    with pytest.raises(KBError, match="fix_catalog.csv missing"):
        load_kb(d)
    d2 = tiny_kb(tmp_path / "b", options=[{"fault_type": "memory_leak", "rank_prior": 1, "fix_id": "x", "fix": "x",
                                          "risk": "extreme", "automation": "a", "source_sheet": "s"}])
    with pytest.raises(KBError, match="unknown risk"):
        load_kb(d2)
    d3 = tiny_kb(tmp_path / "c")
    kb = pd.read_csv(d3 / "knowledge_base.csv").drop(columns=["sources"])
    kb.to_csv(d3 / "knowledge_base.csv", index=False)
    with pytest.raises(KBError, match="sources"):
        load_kb(d3)


def test_tiers_measured_here_beats_prototype_and_prior(tmp_path):
    kb = load_kb(tiny_kb(tmp_path))
    fixes = ranked_fixes(kb, "memory_leak")
    keys = [(f.key, f.evidence) for f in fixes]
    assert keys[0] == ("recreate_container", "measured_here")          # measured on this stack
    assert ("restart_service", "measured_prototype") in keys             # restart_in_place, prototype runs only
    assert keys[-1] == ("scale_out", "prior") and fixes[-1].runbook_id is None   # suggest-only, last
    assert ranked_runbooks(kb, "memory_leak") == ["recreate_container", "restart_service"]


def test_within_a_tier_recovered_then_failed_requests(tmp_path):
    m = [{"live_label": "disk_fill", "fix": "clear_temp_path", "recovered": True, "failed_request_pct": 5.0,
          "time_to_verified_recovery_s": 40, "source_file": "x", "policy": "p"},
         {"live_label": "disk_fill", "fix": "restart_service", "recovered": True, "failed_request_pct": 1.0,
          "time_to_verified_recovery_s": 60, "source_file": "x", "policy": "p"}]
    opts = [{"fault_type": "disk_filling", "rank_prior": 1, "fix_id": "disk_cleanup", "fix": "Clean", "risk": "low",
             "automation": "automatic", "source_sheet": "s"},
            {"fault_type": "disk_filling", "rank_prior": 2, "fix_id": "restart_in_place", "fix": "Restart", "risk": "medium",
             "automation": "needs approval", "source_sheet": "s"}]
    kb = load_kb(tiny_kb(tmp_path, measured=m, options=opts))
    assert ranked_runbooks(kb, "disk_fill") == ["restart_service", "clear_temp_path"]   # both recovered: fewer failed wins


def test_unknown_or_abstained_label():
    assert ranked_runbooks(None, "insufficient_evidence") == []


@pytest.mark.skipif(not REAL.exists(), reason="data/kb not built")
def test_real_kb_keeps_the_top_runbook_for_every_live_label():
    """With the committed knowledge base the proposed (first) runbook equals the old fixed table for every label: each top
    choice is backed by runs measured on this stack. A change here is a behaviour change and must be reported."""
    kb = load_kb(REAL)
    assert kb.summary()["faults"] == 17 and kb.summary()["unreviewed_rows"] == 0
    for label, rbs in CAUSE_RUNBOOKS.items():
        fixes = ranked_fixes(kb, label)
        assert ranked_runbooks(kb, label)[0] == rbs[0], label
        assert fixes[0].evidence == "measured_here" and fixes[0].n >= 10, label
        assert all(f.runbook_id in (None, "restart_service", "recreate_container", "rollback_release", "clear_temp_path")
                   for f in fixes)


def test_label_maps_are_consistent():
    assert set(LIVE_TO_PLAN) == set(CAUSE_RUNBOOKS)
    assert set(FIX_TO_RUNBOOK.values()) <= {"restart_service", "recreate_container", "rollback_release", "clear_temp_path"}


@pytest.mark.skipif(not REAL.exists(), reason="data/kb not built")
def test_engine_records_the_ranking_and_api_serves_the_kb(monkeypatch):
    from fastapi.testclient import TestClient

    from eternalai import api
    from tests.test_autopilot_path import diagnose, make_engine
    e = make_engine("ask-first", "orders", "memory_leak", monkeypatch)
    e.kb = load_kb(REAL)
    inc = diagnose(e, "orders")
    ranking = inc.diagnosis["fix_ranking"]
    assert ranking[0]["key"] == "recreate_container" and ranking[0]["evidence"] == "measured_here"
    assert inc.actions[-1]["runbook_id"] == "recreate_container"
    e.models_loaded, e.det_meta, e.cls_meta, e.rank_meta = {}, None, None, None
    e.latest, e.depfail = {}, {}
    monkeypatch.setattr(api, "engine", e)
    c = TestClient(api.app)
    r = c.get("/kb/memory_leak").json()
    assert r["entry"]["reviewed"] is True and r["ranked_fixes"][0]["key"] == "recreate_container"
    assert c.get("/api/kb/disk_filling").json()["live_label"] == "disk_fill"
    assert c.get("/kb/no_such_fault").status_code == 404
    e.kb = None
    assert c.get("/kb/memory_leak").status_code == 503
