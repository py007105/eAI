"""tools/run_v3_sequence.py fails closed: only fresh results naming this commit and execution, with every check passed."""
import importlib.util
import os
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("seq", ROOT / "tools" / "run_v3_sequence.py")
seq = importlib.util.module_from_spec(spec)
spec.loader.exec_module(seq)


def setup(tmp_path, monkeypatch, text, age_s=0):
    monkeypatch.setattr(seq, "ROOT", tmp_path)
    monkeypatch.setattr(seq, "EXEC_DIR", tmp_path / "exec")
    f = tmp_path / "docs" / "r.md"
    f.parent.mkdir(parents=True)
    f.write_text(text, encoding="utf-8")
    if age_s:
        old = time.time() - age_s
        os.utime(f, (old, old))
    rec = {"start_epoch": time.time() - 10}
    seq.collect(rec, ["docs/r.md", "docs/missing.json"])
    return rec


def ok_text(n="5 of 5", extra=""):
    return f"Commit: `abc1234`; execution ID: `{seq.EXEC_ID}`\n**{n} checks passed**{extra}"


def test_a_fresh_complete_matching_file_passes_and_is_copied(tmp_path, monkeypatch):
    rec = setup(tmp_path, monkeypatch, ok_text())
    assert seq.verdict(rec, "docs/r.md", "abc1234")["status"] == "PASS"
    assert (tmp_path / "exec" / "outputs" / "docs" / "r.md").exists()
    assert rec["outputs"][1] == {"path": "docs/missing.json", "exists": False, "written_during_step": False, "sha256": None}


def test_fail_closed_cases(tmp_path, monkeypatch):
    assert seq.verdict(setup(tmp_path / "a", monkeypatch, ok_text(), age_s=3600), "docs/r.md", "abc1234")["status"] == "FAIL"  # stale
    assert seq.verdict(setup(tmp_path / "b", monkeypatch, ok_text().replace(seq.EXEC_ID, "older")), "docs/r.md", "abc1234")["status"] == "FAIL"
    assert seq.verdict(setup(tmp_path / "c", monkeypatch, ok_text()), "docs/r.md", "other99")["status"] == "FAIL"           # other commit
    assert seq.verdict(setup(tmp_path / "d", monkeypatch, ok_text("4 of 5")), "docs/r.md", "abc1234")["status"] == "FAIL"   # one failed
    assert seq.verdict(setup(tmp_path / "e", monkeypatch, ok_text("4 of 5", "; INCOMPLETE: 1")), "docs/r.md", "abc1234")["status"] == "FAIL"
    assert seq.verdict(setup(tmp_path / "f", monkeypatch, "Commit: `abc1234`; execution ID: `%s`\nrun aborted" % seq.EXEC_ID),
                       "docs/r.md", "abc1234")["status"] == "FAIL"                                                     # partial
    rec = {"start_epoch": time.time(), "outputs": []}
    assert seq.verdict(rec, "docs/r.md", "abc1234")["status"] == "FAIL"                                                # missing
