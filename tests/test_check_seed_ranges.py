import importlib.util
import json
from pathlib import Path

spec = importlib.util.spec_from_file_location("csr", Path(__file__).resolve().parents[1] / "tools" / "check_seed_ranges.py")
csr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(csr)


def test_default_plan_is_clear_of_training_benchmark_and_smoke(tmp_path):
    (tmp_path / "a_1000.json").write_text(json.dumps({"seed": 1000}))
    (tmp_path / "a_1707.json").write_text(json.dumps({"seed": 1707}))
    smoke = tmp_path / "s.jsonl"
    smoke.write_text(json.dumps({"seed": 2008}) + "\n")
    assert csr.check(csr.used_seeds(tmp_path, smoke)) == []


def test_overlaps_are_reported_by_cause(tmp_path):
    (tmp_path / "t.json").write_text(json.dumps({"seed": 3001}))
    used = csr.used_seeds(tmp_path, None)
    assert any("training run" in p and "3001" in p for p in csr.check(used))
    bad = csr.check(used, planned={"x": range(100, 102), "y": range(2500, 2501), "z": range(100, 101)})
    text = " ".join(bad)
    assert "benchmark v1" in text and "smoke block" in text and "overlap" in text
