"""Docker lock: atomic ownership (owner file created with O_EXCL), release only by the owner, schedule kept, parent mode."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import stack_lock  # noqa: E402


def lockfile(tmp_path, last="FREE | last: none"):
    f = tmp_path / "STACK_LOCK.md"
    f.write_text(f"# schedule\n| when | who |\n{last}\n", encoding="utf-8")
    return f


def test_take_and_release_keep_the_schedule(tmp_path):
    f = lockfile(tmp_path)
    tok = stack_lock.take("main", "forecast", "plan-complete@abc", f)
    lines = f.read_text(encoding="utf-8").splitlines()
    assert lines[:2] == ["# schedule", "| when | who |"] and lines[-1].startswith("HELD by main | forecast")
    assert stack_lock.owner(f)["token"] == tok and not stack_lock.is_free(f)
    stack_lock.release("main", "plan-complete@abc", f)
    assert stack_lock.state(f).startswith("FREE | last: main") and stack_lock.owner(f) is None and stack_lock.is_free(f)


def test_acquisition_is_exclusive_even_if_the_display_says_free(tmp_path):
    f = lockfile(tmp_path)
    stack_lock.take("main", "x", "y", f)
    stack_lock._write(f, ["# schedule"], "FREE | edited by hand")        # someone overwrote the display
    with pytest.raises(SystemExit, match="owned by"):
        stack_lock.take("codex", "kind", "z", f)                       # the owner file still decides


def test_display_held_by_an_older_holder_also_blocks(tmp_path):
    f = lockfile(tmp_path, "HELD by main | forecast check | since x")
    with pytest.raises(SystemExit, match="held"):
        stack_lock.take("codex", "kind", "z", f)


def test_only_the_owner_can_release(tmp_path):
    f = lockfile(tmp_path)
    stack_lock.take("main", "x", "y", f)
    with pytest.raises(SystemExit, match="does not own"):
        stack_lock.release("codex", "z", f, token="not-the-token")
    assert stack_lock.owner(f) is not None


def test_parent_mode_keeps_the_lock_held_between_child_steps(tmp_path, monkeypatch):
    f = lockfile(tmp_path)
    tok = stack_lock.take("main", "overnight sequence", "x", f)
    monkeypatch.setenv(stack_lock.PARENT_ENV, "main")
    monkeypatch.setenv(stack_lock.TOKEN_ENV, tok)
    assert stack_lock.take("main", "child step", "x", f) == tok         # verifies ownership, does not re-take
    stack_lock.release("main", "x", f)                                   # no-op in a child
    assert stack_lock.owner(f)["token"] == tok
    monkeypatch.setenv(stack_lock.TOKEN_ENV, "wrong")
    with pytest.raises(SystemExit, match="should own"):
        stack_lock.take("main", "child", "x", f)
    monkeypatch.delenv(stack_lock.PARENT_ENV)
    stack_lock.release("main", "x", f, token=tok)
    assert stack_lock.is_free(f)
