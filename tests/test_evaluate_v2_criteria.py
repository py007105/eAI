"""evaluate_v2_criteria on SYNTHETIC fixture rows only."""
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("c", Path(__file__).resolve().parents[1] / "scripts" / "evaluate_v2_criteria.py")
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)


def fault(arm, scen, seed, **kw):
    s = {"detected": True, "time_to_detect_s": 10.0, "recovered": True, "failed_request_pct": 10.0, "abstained_correctly": None,
         "incidents_opened": 1, "actions_executed": 1}
    s.update(kw)
    r = {"arm": arm, "scenario": scen, "seed": seed, "score": s}
    if arm == c.ASK:
        r["approver"] = {"approved": 1, "approve_failures": 0, "thread_errors": 0, "poll_errors": 0}
    return r


def healthy(arm, scen, seed, **kw):
    s = {"detected": False, "incidents_opened": 0, "actions_executed": 0}
    s.update(kw)
    r = {"arm": arm, "scenario": scen, "seed": seed, "score": s}
    if arm == c.ASK:
        r["approver"] = {"approved": 0, "approve_failures": 0, "thread_errors": 0, "poll_errors": 0}
    return r


def full(mod=None):
    rows, seed = [], 0
    for rep in range(12):
        for s in c.HEALTHY:
            seed += 1
            rows += [healthy(c.AUTO, s, seed), healthy(c.THR, s, seed)]
            if rep < 4:
                rows.append(healthy(c.ASK, s, seed))
    for rep in range(3):
        for s in c.SUPPORTED:
            seed += 1
            rows += [fault(c.AUTO, s, seed), fault(c.ASK, s, seed)]
        seed += 1
        rows.append(fault(c.AUTO, "cpu_burn", seed, detected=True, abstained_correctly=True, recovered=False))
    if mod:
        mod(rows)
    return rows


def run(rows):
    out, have, allpass = c.evaluate(rows)
    return {o["n"]: o["verdict"] for o in out}, allpass, c.render(out, have, allpass)


def test_perfect_fixture_passes_everything_and_allows_v2():
    v, ok, text = run(full())
    assert set(v.values()) == {"PASS"} and ok and "demo may show v2" in text


def test_each_failure_is_reported_as_failed():
    def m(rows):
        for r in rows:
            if r["arm"] == c.ASK and r["scenario"] == "crash":
                r["approver"]["approve_failures"] = 1
    assert run(full(m))[0][1] == "FAIL"

    def m2(rows):
        for r in [r for r in rows if r["arm"] == c.AUTO and r["scenario"] == "traffic_surge"][:3]:
            r["score"]["incidents_opened"] = 1
    assert run(full(m2))[0][2] == "FAIL"

    def m3(rows):
        [r for r in rows if r["arm"] == c.AUTO and r["scenario"] == "good_deploy"][0]["score"]["actions_executed"] = 1
    assert run(full(m3))[0][3] == "FAIL"

    def m4(rows):
        for r in rows:
            if r["arm"] == c.AUTO and r["scenario"] in c.SUPPORTED:
                r["score"]["time_to_detect_s"] = 16.0
    assert run(full(m4))[0][4] == "FAIL"

    def m5(rows):
        for r in [r for r in rows if r["arm"] == c.AUTO and r["scenario"] == "latency"]:
            r["score"]["recovered"] = False
    v, ok, text = run(full(m5))
    assert v[5] == "FAIL" and not ok and "uses v1" in text

    def m6(rows):
        for r in rows:
            if r["arm"] == c.AUTO and r["scenario"] in c.SUPPORTED:
                r["score"]["failed_request_pct"] = 30.0
    assert run(full(m6))[0][6] == "FAIL"

    def m7(rows):
        for r in [r for r in rows if r["scenario"] == "cpu_burn"][:2]:
            r["score"]["abstained_correctly"] = False
    assert run(full(m7))[0][7] == "FAIL"


def test_crash_cell_may_have_one_recovery_but_others_need_two():
    def m(rows):
        cr = [r for r in rows if r["arm"] == c.AUTO and r["scenario"] == "crash"]
        cr[0]["score"]["recovered"] = False
        cr[1]["score"]["recovered"] = False
    assert run(full(m))[0][5] == "PASS"


def test_threshold_restart_comparison_and_incomplete_runs():
    def m(rows):
        for r in [r for r in rows if r["arm"] == c.AUTO and r["scenario"] == "traffic_surge"][:2]:
            r["score"]["incidents_opened"] = 1          # 2/24 is allowed only if threshold_restart is not better
    assert run(full(m))[0][2] == "FAIL"

    def m_both(rows):
        m(rows)
        for r in [r for r in rows if r["arm"] == c.THR and r["scenario"] == "traffic_surge"][:2]:
            r["score"]["incidents_opened"] = 1
    assert run(full(m_both))[0][2] == "PASS"
    v, ok, text = run(full(lambda rows: rows.__delitem__(slice(0, 5))))
    assert "INCOMPLETE" in v.values() and not ok and "not decidable" in text


def test_load_counts_each_arm_scenario_seed_once(tmp_path):
    import json
    rows = full()
    f = tmp_path / "raw.jsonl"
    f.write_text("\n".join(json.dumps(r) for r in rows + [rows[0], rows[5]]))
    assert len(c.load(f)) == len(rows)
