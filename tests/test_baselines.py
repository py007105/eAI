import numpy as np

from engine.baselines import ZScoreDetector, proto_find, upstream, downstream

TOPO = {"web": ["orders", "inventory"], "orders": ["inventory", "payments"], "inventory": [], "payments": []}


def snap(**kw):
    base = dict(mem=60.0, mem_limit=256.0, disk=0.0, disk_limit=300.0, rps=6.0, err=0.0, p95=50.0, cpu=3.0)
    base.update(kw)
    return base


def z(**anom):
    return {m: {"anomalous": v, "hot": v, "z": 5.0 if v else 0.0, "mean": 1.0} for m, v in anom.items()}


def run(sick, **kw):
    snaps = {s: snap() for s in TOPO}
    zs = {s: z(p95=False, err=False, cpu=False, mem=False) for s in TOPO}
    for s, metrics in sick.items():
        zs[s] = z(**{m: (m in metrics) for m in ("p95", "err", "cpu", "mem")})
    normal_rps = {s: 6.0 for s in TOPO}   # traffic is at its normal level unless a test says otherwise
    return proto_find(snaps, zs, kw.get("preds", {}), kw.get("down", {}), kw.get("deploys", {}), normal_rps, 1000.0, TOPO)


def test_topology_helpers():
    assert downstream("web", TOPO) == {"orders", "inventory", "payments"} and upstream("inventory", TOPO) == {"web", "orders"}


def test_root_rule_blames_the_deepest_sick_service_only():
    """Prototype rule: blame a service only if nothing below it is sick; callers are 'affected'."""
    findings, roots, symptomatic = run({"payments": {"err"}, "orders": {"err"}, "web": {"err"}})
    assert roots == {"payments"} and symptomatic == {"payments", "orders", "web"}
    assert {f["service"] for f in findings} == {"payments"}


def test_error_after_recent_deploy_is_a_bad_deploy_else_error_spike():
    f_dep, _, _ = run({"inventory": {"err"}}, deploys={"inventory": 900.0})
    f_no, _, _ = run({"inventory": {"err"}})
    assert f_dep[0]["kind"] == "bad_deploy" and f_no[0]["kind"] == "error_spike"


def test_down_needs_two_consecutive_misses():
    assert run({}, down={"orders": 1})[0] == [] and run({}, down={"orders": 2})[0][0]["kind"] == "down"


def test_cpu_with_normal_traffic_is_runaway_and_with_high_traffic_is_overload():
    findings, _, _ = run({"payments": {"cpu"}})
    assert findings[0]["kind"] == "cpu_runaway"
    snaps = {s: snap(rps=30.0) for s in TOPO}
    zs = {s: z(p95=False, err=False, cpu=(s == "payments"), mem=False) for s in TOPO}
    f2, _, _ = proto_find(snaps, zs, {}, {}, {}, {s: 6.0 for s in TOPO}, 1000.0, TOPO)
    assert f2[0]["kind"] == "overload"


def test_quiet_service_with_empty_forecasts_is_not_anomalous():
    """Regression: preds[s] == {'mem': None, 'disk': None} is a non-empty dict, hence truthy; the prototype port flagged every
    service permanently and opened a bogus incident before any fault."""
    from engine.baselines import proto_anomalous
    quiet_z = z(p95=False, err=False, cpu=False, mem=False)
    assert not proto_anomalous("web", set(), {"web": {"mem": None, "disk": None}}, snap(), quiet_z)
    assert proto_anomalous("web", set(), {"web": {"mem": {"slope": 1.0, "eta_s": 30.0}, "disk": None}}, snap(), quiet_z)
    assert proto_anomalous("web", {"web"}, {}, snap(), quiet_z)
    assert proto_anomalous("web", set(), {}, snap(disk=290.0), quiet_z)          # disk nearly full
    assert proto_anomalous("web", set(), {}, snap(), z(p95=False, err=False, cpu=True, mem=False))


def test_zscore_detector_needs_a_streak_and_learns_only_normal_values():
    zd = ZScoreDetector()
    for _ in range(20):
        zd.update("web", "err", 0.0)
    flags = [zd.update("web", "err", 0.6)["anomalous"] for _ in range(4)]
    assert flags == [False, False, True, True]                 # streak of 3
    assert abs(np.mean(zd.baseline[("web", "err")])) < 1e-9    # the faulty values did not become "normal"
