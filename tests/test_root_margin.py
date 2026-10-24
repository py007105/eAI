"""models/choose_root_margin.py: the margin is the 1% quantile of the top-2 gap on correctly ranked out-of-fold incidents."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("crm", ROOT / "models" / "choose_root_margin.py")
crm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(crm)


def rows():
    right = [{"support_sorted": [0.5 + i / 200, 0.2, 0.2, 0.1], "top1_correct": True} for i in range(100)]   # gaps 0.30..0.795
    wrong = [{"support_sorted": [0.40, 0.38, 0.12, 0.10], "top1_correct": False},                       # gap 0.02
             {"support_sorted": [0.70, 0.10, 0.10, 0.10], "top1_correct": False}]                       # gap 0.60
    return right + wrong


def test_margin_rule():
    r = crm.choose(rows())
    assert abs(r["margin"] - 0.30495) < 1e-6 and r["right_that_would_abstain"] == 1
    assert r["top1_wrong"] == 2 and r["wrong_that_would_abstain"] == 1 and r["wrong_gaps"] == [0.02, 0.6]


def test_engine_reads_the_artifact(tmp_path, monkeypatch):
    from eternalai import artifacts, engine
    monkeypatch.setattr(artifacts, "ARTIFACT_DIR", tmp_path)
    assert engine.load_root_margin() is None
    (tmp_path / "root_margin.json").write_text(json.dumps({"margin": 0.12}), encoding="utf-8")
    assert engine.load_root_margin() == 0.12
