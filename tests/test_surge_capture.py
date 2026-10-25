"""surge_capture analysis on SYNTHETIC runs only."""
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("sc", Path(__file__).resolve().parents[1] / "tools" / "surge_capture.py")
sc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sc)
T0, MB = 1000.0, 1e6


def run(seed, level, inv_peak_mb, incident=None):
    lim = 268.435456 * MB
    prom = {}
    for s in sc.SERVICES:
        peak = inv_peak_mb if s == "inventory" else 66.0
        prom[s] = {"mem": [(T0 + i, (65.0 if i < 10 else peak) * MB) for i in range(-60, 70)], "mem_limit": [(T0, lim)], "rps": [], "start": []}
    return {"seed": seed, "truth": {"t_inject": T0, "params": {"extra_rps_per_thread": level}}, "score": {"t_end": T0 + 60},
            "incidents": [incident] if incident else [], "prom": prom}


LIMITS = {"inventory": 0.2603, "web": 0.2794, "orders": 0.2738, "payments": 0.2492}


def test_exceeds_learned_limit_only_when_the_peak_share_is_above_it():
    low = sc.analyse_run(run(1, 25, 67.0), LIMITS)       # 0.2496 of the limit
    high = sc.analyse_run(run(2, 40, 71.0), LIMITS)      # 0.2645
    assert low["inventory exceeds learned limit"] is False and high["inventory exceeds learned limit"] is True
    assert high["inventory MB peak in surge"] == 71.0 and low["inventory MB before"] == 65.0


def test_incidents_outside_the_run_window_are_ignored_and_causes_listed():
    inc_in = {"opened_t": T0 + 14, "likely_cause": "memory_leak"}
    inc_out = {"opened_t": T0 + 300, "likely_cause": "down"}
    r = run(3, 25, 67.0, inc_in)
    r["incidents"].append(inc_out)
    a = sc.analyse_run(r, LIMITS)
    assert a["incidents opened in run window"] == 1 and a["diagnosed as"] == ["memory_leak"]


def test_summary_by_level_counts_and_fixture_label():
    rows = [sc.analyse_run(run(1, 25, 67.0), LIMITS), sc.analyse_run(run(2, 40, 71.0, {"opened_t": T0 + 14, "likely_cause": "memory_leak"}), LIMITS),
            sc.analyse_run(run(3, 40, 72.0), LIMITS)]
    out = sc.render(rows, LIMITS, fixture=True)
    assert "FIXTURE DATA" in out
    summ = out.split("## Summary by surge level")[1].strip().splitlines()
    cells = lambda s: [c.strip() for c in s.strip("|").split("|")]  # noqa: E731
    header, rows40 = cells(summ[0]), [cells(x) for x in summ[2:] if cells(x)[0] == "40"]
    r = dict(zip(header, rows40[0]))
    assert r["runs"] == "2" and r["runs with an incident"] == "1" and r["inventory: runs exceeding limit"] == "2"
