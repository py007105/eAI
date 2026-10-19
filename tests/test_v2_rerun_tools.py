"""v2_validity_mark, stock_gate and stage3_rerun helpers on SYNTHETIC data only (no docker, no network)."""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))


def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


vm, sg, rr = load("v2_validity_mark"), load("stock_gate"), load("stage3_rerun")

CUT = 1000.0


def row(arm, scen, seed, t_end, ok_probe=None, code=None):
    inc = []
    if ok_probe is not None:
        inc = [{"verification": {"t": ok_probe, "success_rate": 1.0, "last_detail": "HTTP 200"}}]
    if code:
        inc = [{"verification": {"t": t_end - 5, "success_rate": 0.0, "last_detail": code}}]
    return {"arm": arm, "scenario": scen, "seed": seed, "finished_at": "x", "score": {"t_end": t_end}, "incidents": inc}


def rows_of(*rs):
    return {(r["arm"], r["scenario"], r["seed"]): r for r in rs}


def test_cutoff_is_last_completed_checkout_and_rule_is_run_end_after_it():
    rows = rows_of(row("eternalai_ask_first", "crash", 200, 990, ok_probe=CUT), row("eternalai_ask_first", "latency", 201, 1500, code="HTTP 409"),
                   row("eternalai_autopilot", "traffic_surge", 237, 900))
    cut, first409 = vm.cutoff_time(rows)
    assert cut == CUT and first409 == 1495
    inv = vm.classify(rows, cut)
    assert inv[("eternalai_ask_first", "crash", 200)] is False          # ends before the cutoff
    assert inv[("eternalai_ask_first", "latency", 201)] is True
    assert inv[("eternalai_autopilot", "traffic_surge", 237)] is False
    inv2 = vm.classify(rows_of(row("eternalai_ask_first", "crash", 200, 1008, ok_probe=CUT)), cut)
    assert list(inv2.values()) == [True]                                 # a run that ends 8 s after the cutoff is invalid even though it looks clean


def test_plan_same_seed_for_partial_groups_and_fresh_seed_for_fully_invalid_groups():
    rows = rows_of(row("eternalai_ask_first", "error_spike", 202, 900), row("eternalai_autopilot", "error_spike", 202, 1200),
                   row("eternalai_ask_first", "crash", 200, 1300), row("eternalai_autopilot", "crash", 200, 1400),
                   row("eternalai_autopilot", "cpu_burn", 206, 1500))
    inv = vm.classify(rows, CUT)
    _, jobs = vm.plan(rows, inv)
    by = {(j["arm"], j["scenario"]): j for j in jobs}
    assert by[("eternalai_autopilot", "error_spike")]["seed"] == 202 and by[("eternalai_autopilot", "error_spike")]["kind"] == "same-seed"
    assert ("eternalai_ask_first", "error_spike") not in by                # the valid partner is not re-run
    assert by[("eternalai_ask_first", "crash")]["seed"] == by[("eternalai_autopilot", "crash")]["seed"] == 400 and by[("eternalai_ask_first", "crash")]["kind"] == "fresh"
    assert by[("eternalai_autopilot", "cpu_burn")]["seed"] == 406
    order = [j["segment"] for j in jobs]
    assert order == sorted(order, key=lambda s: ["P1", "P1/P2", "P2", "P3"].index(s)) and len(jobs) == 4


def test_fresh_seeds_are_unique_and_below_1000():
    rows = {}
    for seed in (200, 210, 220):
        for arm in ("eternalai_ask_first", "eternalai_autopilot"):
            rows[(arm, "latency", seed + 1)] = row(arm, "latency", seed + 1, 2000)
    _, jobs = vm.plan(rows, vm.classify(rows, CUT))
    seeds = sorted({j["seed"] for j in jobs})
    assert seeds == [401, 411, 421] and all(s < 1000 for s in seeds)


def test_seed_value_matches_the_source_and_gate_logic(tmp_path, monkeypatch):
    repo = Path(__file__).resolve().parents[1]
    src = repo / "app/inventory/main.py"
    if src.exists():                                                      # the docs worktree has no app/; the system tree does
        assert sg.seed_value_in_source(repo) == [sg.SEED_STOCK]
    d = tmp_path / "app/inventory"
    d.mkdir(parents=True)
    (d / "main.py").write_text('("sku-lamp", "Desk lamp", 24.0, 100000), ("sku-mug", "Ceramic mug", 9.5, 100000)')
    assert sg.seed_value_in_source(tmp_path) == [100000]

    state = {"s": {k: 20000 for k in sg.SKUS}, "restocks": 0}
    monkeypatch.setattr(sg, "read_stock", lambda: dict(state["s"]))

    def fake_restock(level=sg.SEED_STOCK):
        state["s"] = {k: level for k in sg.SKUS}
        state["restocks"] += 1
        return len(sg.SKUS)
    monkeypatch.setattr(sg, "restock", fake_restock)
    monkeypatch.setattr(sg, "brain_incidents_between", lambda a, b: [])
    rec = sg.gate()
    assert rec["restocked"] and rec["before"]["sku-mug"] == 20000 and rec["after_restock"]["sku-mug"] == sg.SEED_STOCK and state["restocks"] == 1
    rec = sg.gate()
    assert not rec["restocked"] and state["restocks"] == 1                # above the threshold: nothing happens
    state["s"]["sku-bag"] = sg.THRESHOLD - 1
    assert sg.gate()["restocked"]


def test_gate_aborts_when_restock_or_verification_fails(monkeypatch):
    monkeypatch.setattr(sg, "read_stock", lambda: {k: 10 for k in sg.SKUS})
    monkeypatch.setattr(sg, "brain_incidents_between", lambda a, b: [])
    monkeypatch.setattr(sg, "restock", lambda level=sg.SEED_STOCK: (_ for _ in ()).throw(sg.GateError("boom")))
    with pytest.raises(sg.GateError):
        sg.gate()
    monkeypatch.setattr(sg, "restock", lambda level=sg.SEED_STOCK: len(sg.SKUS))          # claims success but the read-back is still low
    with pytest.raises(sg.GateError):
        sg.gate()
    monkeypatch.setattr(sg, "read_stock", lambda: {"sku-lamp": 1})
    with pytest.raises(sg.GateError):
        sg.gate()


def test_annotate_changes_only_the_target_row(tmp_path):
    p = tmp_path / "r.jsonl"
    a, b = {"arm": "x", "scenario": "crash", "seed": 1}, {"arm": "x", "scenario": "crash", "seed": 2}
    p.write_text(json.dumps(a) + "\n" + json.dumps(b) + "\n")
    assert rr.annotate(p, ("x", "crash", 2), {"before": {"sku-mug": 5}})
    rows = [json.loads(x) for x in p.read_text().splitlines()]
    assert "stock" not in rows[0] and rows[1]["stock"]["before"]["sku-mug"] == 5
    assert rr.finished(p) == {("x", "crash", 1), ("x", "crash", 2)}


def test_combine_drops_only_listed_originals_and_rejects_duplicates():
    cb = load("v2_combine")
    a = json.dumps({"arm": "x", "scenario": "crash", "seed": 1, "score": {"t_end": 5.0}})
    b = json.dumps({"arm": "x", "scenario": "crash", "seed": 2, "score": {"t_end": 6.0}})
    new = json.dumps({"arm": "x", "scenario": "crash", "seed": 2, "score": {"t_end": 99.0}})
    out, dropped = cb.combine([a, b], [new], [{"arm": "x", "scenario": "crash", "seed": 2, "t_end": 6.0}])
    assert out == [a, new] and dropped == 1
    with pytest.raises(ValueError):
        cb.combine([a, b], [new], [])          # same (arm, scenario, seed) twice without an invalid marker
