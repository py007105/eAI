"""memguard and safe_collect helpers, with no stack and no real memory reading."""
import importlib.util
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "tools"


def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


mg, sc = load("memguard"), load("safe_collect")


def test_guard_returns_at_once_when_memory_is_enough_and_when_disabled():
    assert mg.wait_for_memory(1.0, free=lambda: 3.0, sleep=lambda s: None) == 0.0
    assert mg.wait_for_memory(0, free=lambda: 0.0, sleep=lambda s: None) == 0.0


def test_guard_waits_logs_and_continues_when_memory_recovers():
    seq = iter([0.5, 0.6, 0.7, 1.4])
    logs = []
    waited = mg.wait_for_memory(1.0, poll_s=30, free=lambda: next(seq), sleep=lambda s: None, log=lambda m, **k: logs.append(m))
    assert waited == 90 and any("waiting" in m for m in logs) and "continuing" in logs[-1]


def test_guard_gives_up_after_the_maximum_wait_instead_of_starting():
    with pytest.raises(TimeoutError):
        mg.wait_for_memory(1.0, poll_s=60, max_wait_s=120, free=lambda: 0.2, sleep=lambda s: None, log=lambda *a, **k: None)


def test_free_ram_reads_a_plausible_number_on_this_machine():
    assert 0.05 < mg.free_ram_gb() < 4096


def test_atomic_write_leaves_no_partial_file_when_the_write_fails(tmp_path, monkeypatch):
    target = tmp_path / "run_1800.json"
    sc.atomic_write_text(target, "{}")
    assert target.read_text() == "{}" and not list(tmp_path.glob("*.tmp"))
    monkeypatch.setattr(sc.os, "replace", lambda a, b: (_ for _ in ()).throw(OSError("killed")))
    with pytest.raises(OSError):
        sc.atomic_write_text(tmp_path / "other.json", "{}")
    assert not (tmp_path / "other.json").exists()                 # the real name never holds half a file


def test_jobs_must_be_in_the_unused_training_block():
    assert sc.parse_jobs(["crash:1824", "traffic_surge:1801"]) == [("crash", 1824), ("traffic_surge", 1801)]
    for bad in ("crash:1707", "crash:2000", "crash:105"):
        with pytest.raises(SystemExit):
            sc.parse_jobs([bad])


def test_a_finished_run_is_skipped_without_touching_the_stack(tmp_path):
    (tmp_path / "crash_1824.json").write_text("{}")
    assert sc.collect_one("crash", 1824, tmp_path, None, [], 99.0) is False      # would block on memory if it started; it returns first
