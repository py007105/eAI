"""Evaluator opt-in options for the forecast check: `variant: gradual` (slow disk fill) and `observe_full` (no early end).
Benchmarks leave both unset; then injection and the early end behave exactly as before."""
import types

from fastapi.testclient import TestClient

from tests.test_network_lockdown import evaluator  # noqa: F401  (fixture)


def client(main, monkeypatch):
    monkeypatch.setenv("ETERNALAI_APPROVAL_TOKEN", "test-token-123")
    started = []
    monkeypatch.setattr(main.threading, "Thread", lambda target, args, daemon: types.SimpleNamespace(start=lambda: started.append(args)))
    return TestClient(main.app), {"X-Approval-Token": "test-token-123"}, started


def test_variant_only_for_disk_fill(evaluator, monkeypatch):
    main = evaluator("test-chaos-token")
    c, h, started = client(main, monkeypatch)
    assert c.post("/runs", json={"scenario": "latency", "variant": "gradual"}, headers=h).status_code == 400
    assert c.post("/runs", json={"scenario": "disk_fill", "variant": "fast"}, headers=h).status_code == 400
    assert c.post("/runs", json={"scenario": "disk_fill", "variant": "gradual"}, headers=h).status_code == 200
    assert started[0][1].variant == "gradual"


def run_execute(main, monkeypatch, tmp_path, req_body, incidents):
    """Drive _execute with a fake clock, a fake injector and a brain whose incident is already closed."""
    clock = {"t": 1000.0}
    monkeypatch.setattr(main.time, "time", lambda: clock["t"])
    monkeypatch.setattr(main.time, "sleep", lambda s: clock.__setitem__("t", clock["t"] + s))
    calls = []
    monkeypatch.setattr(main, "inj", types.SimpleNamespace(
        restore=lambda dirty: False,
        inject=lambda *a: calls.append(a) or {"p": 1}))
    monkeypatch.setattr(main, "_wait_quiet", lambda *a: True)
    monkeypatch.setattr(main, "settle_seconds", lambda *a: 0)
    monkeypatch.setattr(main, "_failed_pct", lambda *a: 0.0)
    monkeypatch.setattr(main, "_eai_incidents", lambda: incidents(clock["t"]))
    monkeypatch.setattr(main, "score_run", lambda truth, inc, pct, t_end: {"t_end": t_end})
    monkeypatch.setattr(main, "TRUTH", tmp_path)
    monkeypatch.setattr(main, "RESULTS", tmp_path / "results.jsonl")
    req = main.RunRequest(**req_body)
    main.runs["r"] = {"run_id": "r", "state": "running", "seed": 1, "_scenario": req_body["scenario"], "_target": "orders"}
    t0 = clock["t"]
    main._execute("r", req)
    return main.runs["r"]["_result"]["t_end"] - t0, calls


def closed(now):
    return [{"opened_t": 1001.0, "status": "escalated", "closed_t": 1004.0}]


def test_default_run_ends_early_and_injects_as_before(evaluator, monkeypatch, tmp_path):
    main = evaluator("test-chaos-token")
    dur, calls = run_execute(main, monkeypatch, tmp_path, {"scenario": "memory_leak", "timeout_s": 150}, closed)
    assert dur < 30 and len(calls[0]) == 3          # ended a few seconds after the incident closed; old inject signature


def test_observe_full_runs_to_the_timeout(evaluator, monkeypatch, tmp_path):
    main = evaluator("test-chaos-token")
    dur, _ = run_execute(main, monkeypatch, tmp_path, {"scenario": "memory_leak", "timeout_s": 150, "observe_full": True}, closed)
    assert dur >= 150


def test_gradual_variant_is_passed_to_the_injector(evaluator, monkeypatch, tmp_path):
    main = evaluator("test-chaos-token")
    _, calls = run_execute(main, monkeypatch, tmp_path, {"scenario": "disk_fill", "variant": "gradual", "observe_full": True,
                                                         "timeout_s": 20}, closed)
    assert calls[0][-1] == "gradual"


def test_injector_gradual_disk_fill(evaluator):
    evaluator("test-chaos-token")              # puts evaluator/ on sys.path
    import importlib
    import random
    import sys
    sys.modules.pop("scenarios", None)        # the fixture stubbed Injector; load the real class (no Docker: __new__ only)
    scenarios = importlib.import_module("scenarios")
    sent = []
    inj = scenarios.Injector.__new__(scenarios.Injector)
    inj._chaos = lambda svc, kind, value=0: sent.append((svc, kind, value))
    p = inj.inject("disk_fill", "orders", random.Random(3), "gradual")
    assert sent[0][1] == "disk_stream" and sent[0][2] in (2, 3, 4) and p["variant"] == "gradual"
    sent.clear()
    p = inj.inject("disk_fill", "orders", random.Random(3))
    assert sent[0][1] == "disk_burst" and "variant" not in p
