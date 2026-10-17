"""Regression: a run must not be reported finished until the stack has been restored.

Before the fix the evaluator set state="finished" first and restored afterwards, so a caller that started the
next run immediately collided with the previous restore ("expected 1 container for web, found 0").
No Docker is used: the injector is replaced by a fake."""
import importlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def ev(tmp_path, monkeypatch):
    monkeypatch.setenv("TRUTH_DIR", str(tmp_path / "truth"))  # never touch a real /truth
    monkeypatch.syspath_prepend(str(ROOT / "evaluator"))
    import scenarios

    class FakeInjector:
        def __init__(self, *a, **k):
            self.log = []

        def restore(self, dirty=None):
            self.log.append(("restore", sorted(dirty or []), main.runs[self.run_id]["state"]))
            return False

        def inject(self, scenario, svc, rng):
            self.log.append(("inject", scenario, svc))
            return {}

    monkeypatch.setattr(scenarios, "Injector", FakeInjector)
    for m in ("main", "scoring", "timing"):
        sys.modules.pop(m, None)
    main = importlib.import_module("main")
    monkeypatch.setattr(main.time, "sleep", lambda s: None)
    monkeypatch.setattr(main, "_eai_incidents", lambda: [])
    monkeypatch.setattr(main, "_failed_pct", lambda a, b: 0.0)
    monkeypatch.setattr(main, "_wait_quiet", lambda *a, **k: True)
    yield main
    sys.modules.pop("main", None)


def start(main, scenario="latency", target="orders"):
    main.runs["r1"] = {"run_id": "r1", "state": "running", "started": 0, "seed": 1, "blind": False,
                       "_scenario": scenario, "_target": target}
    main.inj.run_id = "r1"
    return main.RunRequest(scenario=scenario, target=target, timeout_s=1, healthy_s=1)


def test_state_is_finished_only_after_final_restore(ev):
    req = start(ev)
    ev._execute("r1", req)
    restores = [e for e in ev.inj.log if e[0] == "restore"]
    assert len(restores) == 2                       # one before the injection, one after the run
    assert restores[1][2] == "running"              # while the final restore ran, the run was still "running"
    assert ev.runs["r1"]["state"] == "finished"
    assert ev.runs["r1"]["_result"]["t_end"] > 0    # the observation end is reported for data collection


def test_failed_restore_marks_run_failed_not_finished(ev, monkeypatch):
    req = start(ev)
    calls = {"n": 0}

    def flaky(dirty=None):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("expected 1 container for web, found 0")
        return False
    monkeypatch.setattr(ev.inj, "restore", flaky)
    ev._execute("r1", req)
    st = ev.runs["r1"]
    assert st["state"] == "failed" and "found 0" in st["error"] and "_result" not in st


def test_truth_dir_is_configurable_and_not_the_system_root(ev, tmp_path):
    assert str(ev.TRUTH).startswith(str(tmp_path))
