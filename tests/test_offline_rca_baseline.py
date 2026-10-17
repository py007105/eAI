"""offline_rca_baseline on a tiny synthetic fixture only (no real data)."""
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd

spec = importlib.util.spec_from_file_location("offline_rca_baseline", Path(__file__).resolve().parents[1] / "scripts" / "offline_rca_baseline.py")
ob = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ob)


def fixture(n_runs=6):
    """Each run: the target service has large z on one signal, the others near zero. rel covers every delay."""
    rows = []
    for i in range(n_runs):
        tgt = ob.SERVICES[i % 4]
        for rel in ob.DELAYS:
            for s in ob.SERVICES:
                big = 8.0 if s == tgt else 0.3
                rows.append({"run": f"r{i}", "scenario": "crash" if i % 2 else "latency", "target": tgt, "service": s, "rel": float(rel),
                             "lat_z": big, "cpu_per_req_z": 0.1, "mem_z": 0.1, "error_ratio_z": big / 2})
    rows.append({"run": "h", "scenario": "traffic_surge", "target": "web", "service": "web", "rel": 10.0,
                 "lat_z": 9, "cpu_per_req_z": 0, "mem_z": 0, "error_ratio_z": 0})
    return pd.DataFrame(rows)


def test_healthy_scenarios_are_excluded_and_incident_count_is_runs_times_delays():
    res = ob.evaluate(fixture())
    assert set(res.run) == {f"r{i}" for i in range(6)}
    assert len(res[res.method == "baro"]) == 6 * len(ob.DELAYS)


def test_clear_signal_is_found_by_baro_and_errors_and_walk_but_random_is_not_perfect():
    res = ob.evaluate(fixture())
    for m in ("baro", "errors", "walk"):
        assert res[res.method == m].top1.mean() == 1.0
    assert res[res.method == "random"].top1.mean() < 1.0


def test_walk_prefers_the_anomalous_node_and_is_a_permutation():
    order = ob.rank_walk({"web": 0.1, "orders": 0.1, "inventory": 9.0, "payments": 0.1})
    assert order[0] == "inventory" and sorted(order) == sorted(ob.SERVICES)


def test_missing_signals_count_as_zero_not_as_anomalous():
    rows = pd.DataFrame({"lat_z": [np.nan, 5.0], "error_ratio_z": [np.nan, 0.0]}, index=["web", "orders"])
    sc = ob.anomaly_scores(rows)
    assert sc["web"] == 0.0 and sc["orders"] == 5.0 and sc["inventory"] == 0.0


def test_incident_needs_all_four_services():
    df = fixture()
    df = df[~((df.run == "r0") & (df.service == "payments"))]
    res = ob.evaluate(df)
    assert "r0" not in set(res.run)


def test_bootstrap_resamples_runs_and_render_is_labelled_offline_and_fixture():
    res = ob.evaluate(fixture())
    m, lo, hi = ob.pooled_by_run(res[res.method == "baro"], "top1")
    assert m == 1.0 and lo == 1.0 and hi == 1.0
    out = ob.render(res, fixture=True)
    assert "FIXTURE DATA" in out and "OFFLINE" in out and "RE2/RE3" in out
