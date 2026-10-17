"""Tests for scripts/render_results.py on SYNTHETIC rows only. Nothing here describes the system; the numbers are made up so that the
expected outputs can be computed by hand."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import render_results as rr  # noqa: E402

SC_INDEX = {s: i for i, s in enumerate(["crash", "latency", "error_spike", "memory_leak", "disk_fill", "bad_deploy", "cpu_burn", "traffic_surge", "good_deploy"])}


def row(arm, scen, rep, **score):
    base = {"detected": True, "time_to_detect_s": 10.0, "diagnosis_top1": True, "diagnosis_top3": True, "recovered": True,
            "time_to_verified_recovery_s": 40.0, "failed_request_pct": 5.0, "false_alerts": 0, "harmful_interventions": 0,
            "abstained_correctly": None, "incidents_opened": 1, "actions_executed": 1, "final_status": "recovered"}
    if scen in rr.HEALTHY:
        base.update(detected=False, time_to_detect_s=None, diagnosis_top1=None, diagnosis_top3=None, recovered=None, time_to_verified_recovery_s=None,
                    failed_request_pct=0.0, incidents_opened=0, actions_executed=0, final_status=None)
    if arm == "no_action":
        base.update(detected=False, time_to_detect_s=None, diagnosis_top1=False, diagnosis_top3=False, recovered=False,
                    time_to_verified_recovery_s=None, failed_request_pct=60.0, incidents_opened=0, actions_executed=0, final_status="undetected")
    base.update(score)
    return {"arm": arm, "scenario": scen, "seed": 100 + 10 * rep + SC_INDEX[scen], "rep": rep, "target": "web", "params": {},
            "score": base, "incidents": [], "brain_status": {}, "system_commit": "FIXTURE"}


@pytest.fixture
def fixture_file(tmp_path):
    rows = [row(a, s, r) for a in rr.ARMS for s in rr.SCENARIOS for r in range(5)]
    # one deliberate non-recovery, one claimed recovery that contradicts the no-action baseline, one cell with distinct values
    for x in rows:
        if x["arm"] == "eternalai_autopilot" and x["scenario"] == "crash" and x["rep"] == 0:
            x["score"].update(recovered=False, final_status="escalated", time_to_verified_recovery_s=None)
        if x["arm"] == "threshold_restart" and x["scenario"] == "latency" and x["rep"] == 1:
            x["score"]["failed_request_pct"] = 99.0          # claims recovered with more failures than no_action's 60
        if x["arm"] == "eternalai_autopilot" and x["scenario"] == "error_spike":
            x["score"]["failed_request_pct"] = [1.0, 2.0, 3.0, 4.0, 5.0][x["rep"]]
    p = tmp_path / "fixture_rows.jsonl"
    p.write_text("\n".join(json.dumps(x) for x in rows))
    return p


def render(path, tmp_path, extra=()):
    out = tmp_path / "out.md"
    subprocess.run([sys.executable, str(ROOT / "scripts" / "render_results.py"), "--raw", str(path), "--out", str(out), "--fixture",
                    "--triage", str(tmp_path / "none.json"), "--harness-failures", str(tmp_path / "none2.json"), *extra], check=True)
    return out.read_text(encoding="utf-8")


def test_output_is_clearly_marked_fixture(fixture_file, tmp_path):
    text = render(fixture_file, tmp_path)
    assert "FIXTURE DATA, NOT RESULTS" in text and text.startswith("# Held-out benchmark results (FIXTURE)")


def test_refuses_to_write_fixture_output_to_the_real_results_path(fixture_file):
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "render_results.py"), "--raw", str(fixture_file), "--fixture"],
                       capture_output=True, text=True, cwd=ROOT)
    assert r.returncode != 0 and "refusing" in (r.stderr + r.stdout)


def test_accounting_counts_225_and_keeps_every_row(fixture_file, tmp_path):
    text = render(fixture_file, tmp_path)
    assert "distinct (arm, scenario, seed) runs: 225 of 225 planned; duplicate rows: 0" in text
    assert "cells not at 5 runs: none" in text and "no run was dropped" in text


def test_complete_fixture_has_no_incomplete_banner(fixture_file, tmp_path):
    assert "INCOMPLETE" not in render(fixture_file, tmp_path)


def test_incomplete_benchmark_gets_banner_and_per_cell_counts(fixture_file, tmp_path):
    rows = [json.loads(x) for x in fixture_file.read_text().splitlines()]
    part = [x for x in rows if not (x["arm"] in ("prototype_rules", "no_action") or (x["arm"] == "eternalai_ask_first" and x["rep"] > 1))]
    p = tmp_path / "partial.jsonl"
    p.write_text("\n".join(json.dumps(x) for x in part))
    text = render(p, tmp_path)
    assert f"INCOMPLETE: {len(part)} of 225 planned runs" in text
    assert "must not be read as a ranking" in text
    line = next(x for x in text.splitlines() if x.startswith("| eternalai_ask_first"))
    cells = lambda s: [c.strip() for c in s.strip("|").split("|")][1:]  # noqa: E731
    assert cells(line) == ["2"] * 9                       # two runs in each of the nine scenarios
    assert cells(next(x for x in text.splitlines() if x.startswith("| no_action"))) == ["0"] * 9
    assert "FIXTURE DATA, NOT RESULTS" in text           # fixture banner still present


def test_cell_shows_all_five_raw_values_with_mean_and_range(fixture_file, tmp_path):
    text = render(fixture_file, tmp_path)
    line = next(x for x in text.splitlines() if x.startswith("| error_spike | eternalai_autopilot |") and "1.00 2.00 3.00 4.00 5.00" in x)
    assert "| 3.00 | 1.00 to 5.00 | 5 |" in line


def test_non_recovery_is_listed_and_unclassified_without_a_triage_entry(fixture_file, tmp_path):
    text = render(fixture_file, tmp_path)
    assert "| eternalai_autopilot | crash | 100 | escalated | unclassified | - |" in text
    assert "- non-recoveries: 1; classified: 0" in text


def test_triage_entry_is_picked_up(fixture_file, tmp_path):
    tri = tmp_path / "triage.json"
    tri.write_text(json.dumps([{"arm": "eternalai_autopilot", "scenario": "crash", "seed": 100, "class": "c", "evidence": "docs/postmortems/x.md"}]))
    out = tmp_path / "o.md"
    subprocess.run([sys.executable, str(ROOT / "scripts" / "render_results.py"), "--raw", str(fixture_file), "--out", str(out), "--fixture",
                    "--triage", str(tri), "--harness-failures", str(tmp_path / "n.json")], check=True)
    assert "| eternalai_autopilot | crash | 100 | escalated | c | docs/postmortems/x.md |" in out.read_text(encoding="utf-8")


def test_consistency_check_flags_recovery_with_more_failures_than_no_action(fixture_file, tmp_path):
    text = render(fixture_file, tmp_path)
    assert "threshold_restart / latency / seed 111: claimed recovered with 99.00% failed vs 60.00% with no action" in text


def test_pooled_recovery_rate_and_interval_are_computed_over_runs(fixture_file, tmp_path):
    d = rr.load(fixture_file)
    p = rr.pooled(d, "eternalai_autopilot")
    assert p["supported runs"] == 30 and p["recovery rate, self-reported"].startswith("96.7 [")      # 29 of 30 recovered
    assert rr.boot_ci([1.0] * 29 + [0.0])[0] == pytest.approx(29 / 30)


def test_independent_measure_comes_first_and_banner_states_limits(fixture_file, tmp_path):
    out = render(fixture_file, tmp_path)
    assert "Template reports only" in out and "Recovery is self-reported" in out
    assert out.index("## 2. The independent measure first") < out.index("SELF-REPORTED by the system") < out.index("## 4. Pooled")
    assert out.index("Consistency check of self-reported recovery") < out.index("## 3.")
    assert "verified recovery" not in out.lower().replace("never independently verified", "")


def test_paired_difference_uses_matching_seeds(fixture_file):
    d = rr.load(fixture_file)
    diff = rr.paired_diff(d, "eternalai_autopilot", "no_action", "failed_pct", rr.SUPPORTED)
    # autopilot is 5.0 except error_spike (mean 3.0, 5 of 30 runs); no_action is 60.0 everywhere
    expected = ((25 * 5.0 + 5 * 3.0) / 30) - 60.0
    assert diff[0] == pytest.approx(expected) and diff[3] == 30


def test_v2_side_by_side_section_appears_only_with_a_v2_file(fixture_file, tmp_path):
    assert "v1 and v2 side by side" not in render(fixture_file, tmp_path)
    with_v2 = render(fixture_file, tmp_path, ["--raw-v2", str(fixture_file)])
    import re
    assert "## 8. v1 and v2 side by side" in with_v2
    assert re.search(r"\| v1\s+\|", with_v2) and re.search(r"\| v2\s+\|", with_v2)   # markdown pads the cells
