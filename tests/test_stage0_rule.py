"""The Stage 0 decision rule on synthetic facts: the rule is fixed in Amendment 4 before any data exists."""
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("s0", Path(__file__).resolve().parents[1] / "scripts" / "stage0_telemetry.py")
s0 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s0)


def facts(web_before=66.8, web_inc=1.0, inv_before=65.3, inv_inc=2.0):
    return {"web": {"before_mb": web_before, "peak_mb": web_before + web_inc, "increment_mb": web_inc},
            "inventory": {"before_mb": inv_before, "peak_mb": inv_before + inv_inc, "increment_mb": inv_inc}}


def test_qualifies_needs_both_runs_and_both_services():
    assert s0.qualifies([facts(), facts()])
    assert not s0.qualifies([facts(), facts(web_inc=9.5)])                 # one run with the v1-style +9.5 MB web surge
    assert not s0.qualifies([facts(inv_before=72.6), facts()])             # inventory already ratcheted 7 MB above training
    assert not s0.qualifies([facts(), None]) and not s0.qualifies([])      # a missing run cannot qualify
    assert s0.qualifies([facts(web_inc=3.0), facts(inv_before=68.3)])      # limits are inclusive (3.0 MB)


def test_choice_order_is_t3_then_t1_then_t2():
    ok, bad = [facts(), facts()], [facts(web_inc=9.0), facts(web_inc=9.0)]
    assert s0.decide({"T1": ok, "T2": ok, "T3": ok})[0] == "T3"
    assert s0.decide({"T1": ok, "T2": ok, "T3": bad})[0] == "T1"
    assert s0.decide({"T1": bad, "T2": ok, "T3": bad})[0] == "T2"


def test_if_nothing_qualifies_t3_is_used_and_the_finding_is_recorded():
    bad = [facts(web_inc=9.0), facts(web_inc=9.0)]
    c, q, why = s0.decide({"T1": bad, "T2": bad, "T3": bad})
    assert c == "T3" and not any(q.values()) and "does not explain" in why


def test_run_facts_reads_increment_and_median_from_the_series():
    t0, mb = 1000.0, 1e6
    mem = [(t0 + i, (67.0 if i < 10 else 70.0) * mb) for i in range(-60, 70)]
    run = {"truth": {"t_inject": t0}, "score": {"t_end": t0 + 60}, "prom": {"web": {"mem": mem}, "inventory": {"mem": mem}}}
    f = s0.run_facts(run)
    assert f["web"] == {"before_mb": 67.0, "peak_mb": 70.0, "increment_mb": 3.0}
