"""Resuming evaluation v3: only missing registered cases may be added, each once, and the original rows stay unchanged."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("cases", ROOT / "scripts" / "eval_v3_cases.py")
cases = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cases)


def row(arm, scen, seed, x=0):
    return {"arm": arm, "scenario": scen, "seed": seed, "score": {"x": x}}


def test_plan_has_50_unique_cases_with_the_seed_rule():
    p = cases.planned_cases()
    assert len(p) == 50 and len(set(p)) == 50
    assert sum(a == "no_action" for a, _, _ in p) == 5
    assert all(s == 600 + 10 * ((s - 600) // 10) + cases.SCENARIOS.index(sc) for _, sc, s in p)


def test_the_recorded_execution_is_a_prefix_of_the_plan():
    raw = ROOT / "results" / "benchmark-v3" / "20261024T001813-4cedc8bf" / "raw.jsonl"
    rows = cases.rows(raw)
    assert [cases.key(r) for r in rows] == cases.planned_cases()[:26]
    assert len(cases.missing_cases(rows)) == 24


def test_valid_complete_resumption():
    plan = cases.planned_cases()
    orig = [row(*c) for c in plan[:26]]
    v = cases.check_resume(orig, orig + [row(*c) for c in plan[26:]])
    assert v["valid"] and not v["still_missing"] and v["added"] == 24


def test_invalid_resumptions_are_detected():
    plan = cases.planned_cases()
    orig = [row(*c) for c in plan[:26]]
    rest = [row(*c) for c in plan[26:]]
    assert cases.check_resume(orig, orig + rest + [rest[0]])["duplicates"]                       # a case twice
    assert cases.check_resume(orig, orig + [row(*plan[0], x=1)] + rest)["added_but_not_missing"]   # a finished case rerun
    changed = [dict(orig[0], score={"x": 9})] + orig[1:]
    assert not cases.check_resume(orig, changed + rest)["original_rows_unchanged"]                 # original replaced
    assert cases.check_resume(orig, orig + [row("eternalai_autopilot", "crash", 999)])["unplanned"]
    part = cases.check_resume(orig, orig + rest[:5])
    assert part["valid"] and len(part["still_missing"]) == 19                                       # valid but incomplete
