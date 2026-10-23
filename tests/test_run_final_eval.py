"""scripts/run_final_eval.py: the v3 report is rendered only from raw rows (synthetic rows here)."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("rfe", ROOT / "scripts" / "run_final_eval.py")
rfe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rfe)


def row(arm, sc, seed, failed, executed=False, verdict="execute", recovered=False, harmful=0):
    acts = [{"runbook_id": "restart_service", "executed": executed, "verdict": verdict}] if arm != "no_action" else []
    return {"arm": arm, "scenario": sc, "seed": seed, "system_commit": "abc1234", "policy_file": "default.yaml",
            "incidents": [{"actions": acts}] if acts else [],
            "score": {"detected": arm != "no_action", "recovered": recovered, "failed_request_pct": failed,
                      "harmful_interventions": harmful}}


def test_render(tmp_path, monkeypatch):
    raw, out = tmp_path / "raw.jsonl", tmp_path / "v3.md"
    rows = [row("eternalai_autopilot", "memory_leak", 603, 5.0, verdict="needs_approval"),
            row("eternalai_autopilot", "memory_leak", 613, 7.0, verdict="expired_unapproved"),
            row("eternalai_autopilot", "crash", 600, 20.0, executed=True, recovered=True),
            row("no_action", "memory_leak", 603, 0.5), row("no_action", "memory_leak", 613, 0.7)]
    raw.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    monkeypatch.setattr(rfe, "RAW", raw)
    monkeypatch.setattr(rfe, "OUT", out)
    monkeypatch.setattr(rfe, "ROOT", tmp_path)
    rfe.render()
    text = out.read_text(encoding="utf-8")
    assert "| eternalai_autopilot | memory_leak | 2 | 2/2 | 0/2 | 0/2 | 2/2 | 6.00 / 6.00 / 5.0-7.0 | 0 | - |" in text
    assert "| eternalai_autopilot | crash | 1 | 1/1 | 1/1 | 1/1 | 0/1 |" in text
    assert "| 603 | 5.0 | 0.5 |" in text and "| 613 | 7.0 | 0.7 |" in text
    assert "policy files: ['default.yaml']" in text and "system commits: ['abc1234']" in text
