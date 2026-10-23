"""The lock helpers change only the last line of the schedule file and refuse a lock held by another session."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import stack_lock  # noqa: E402


def test_take_and_release_keep_the_schedule(tmp_path):
    f = tmp_path / "STACK_LOCK.md"
    f.write_text("# schedule\n| when | who |\nFREE | last: none\n", encoding="utf-8")
    stack_lock.take("main", "forecast", "plan-complete@abc", f)
    lines = f.read_text(encoding="utf-8").splitlines()
    assert lines[:2] == ["# schedule", "| when | who |"] and lines[-1].startswith("HELD by main | forecast")
    with pytest.raises(SystemExit, match="held by another"):
        stack_lock.take("codex", "kind", "x", f)
    stack_lock.release("main", "plan-complete@abc", f)
    assert f.read_text(encoding="utf-8").splitlines()[-1].startswith("FREE | last: main")
    assert stack_lock.state(f).startswith("FREE")


def test_missing_file_counts_as_free(tmp_path):
    f = tmp_path / "none.md"
    assert stack_lock.state(f) == "FREE"
    stack_lock.take("main", "x", "y", f)
    assert stack_lock.state(f).startswith("HELD by main")


def test_parent_mode_keeps_the_lock_held_between_child_steps(tmp_path, monkeypatch):
    f = tmp_path / "STACK_LOCK.md"
    f.write_text("# schedule\nFREE | last: none\n", encoding="utf-8")
    stack_lock.take("main", "overnight sequence", "x", f)               # the parent takes it once
    monkeypatch.setenv(stack_lock.PARENT_ENV, "main")                   # what the parent passes to its children
    stack_lock.take("main", "child step", "x", f)                       # no-op, but checks it is still held
    stack_lock.release("main", "x", f)                                  # no-op in a child
    assert stack_lock.state(f).startswith("HELD by main | overnight sequence")
    monkeypatch.delenv(stack_lock.PARENT_ENV)
    stack_lock.release("main", "x", f)                                  # the parent releases it at the end
    assert stack_lock.state(f).startswith("FREE")


def test_a_child_refuses_to_run_if_the_parent_lost_the_lock(tmp_path, monkeypatch):
    f = tmp_path / "STACK_LOCK.md"
    f.write_text("HELD by codex | kind | since x\n", encoding="utf-8")
    monkeypatch.setenv(stack_lock.PARENT_ENV, "main")
    with pytest.raises(SystemExit, match="parent sequence should hold"):
        stack_lock.take("main", "child", "x", f)
