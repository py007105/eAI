"""The generated blocks of the documents are current, resolve every placeholder, and the Wilson helper behaves."""
import importlib.util
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "tools"
sys.path.insert(0, str(SCRIPTS))


def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


bd = load("build_docs")
rv = load("render_v2_report")


def test_wilson_known_values():
    lo, hi = rv.wilson(18, 18)
    assert 0.81 < lo < 0.83 and hi == 1.0
    lo, hi = rv.wilson(0, 24)
    assert lo == 0.0 and 0.13 < hi < 0.15


def test_generated_blocks_are_current_and_have_no_placeholder():
    assert bd.build(check=True) == []
    for rel in bd.TARGETS.values():
        assert not re.search(r"\{\{[a-z0-9_]+\}\}", (ROOT / rel).read_text(encoding="utf-8")), rel


def test_unknown_placeholder_is_an_error():
    import pytest
    with pytest.raises(KeyError):
        bd.fill("{{nope}}", {"a": 1}, "x")
