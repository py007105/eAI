import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("p", Path(__file__).resolve().parents[1] / "scripts" / "plan_v2_seeds.py")
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)


def test_simulation_matches_known_recorded_runs():
    # recorded in results/benchmark-v1: seed 100 crash -> orders; seed 104 disk_fill -> web; seed 107 traffic_surge -> web at 25
    assert p.sim_target("crash", 100) == "orders" and p.sim_target("disk_fill", 104) == "web"
    assert p.sim_target("traffic_surge", 107) == "web" and p.sim_surge_level(107) == 25


def test_validate_reports_mismatches():
    n, bad = p.validate([{"scenario": "crash", "seed": 100, "target": "orders", "params": {}}], [{"scenario": "crash", "seed": 100, "target": "web", "params": {}}])
    assert n == 2 and bad == [("training", "crash", 100)]


def test_training_plan_is_unique_inside_the_block_covers_the_wishlist_and_never_uses_cpu_burn():
    jobs = p.plan_training()
    seeds = [j["seed"] for j in jobs]
    assert len(set(seeds)) == len(seeds) and all(1800 <= s <= 1999 for s in seeds)
    assert len(jobs) == len(p.training_wishlist()) and all(j["scenario"] != "cpu_burn" for j in jobs)
    assert sum(1 for j in jobs if j["surge_level"] == 25) == 6 and sum(1 for j in jobs if j["surge_level"] == 40) == 6
    assert all(p.sim_target(j["scenario"], j["seed"]) == j["target"] for j in jobs)


def test_eval_seeds_disjoint_from_training_v1_and_smoke_blocks_and_have_both_surge_levels():
    ev = p.eval_seeds()
    seeds = [e["seed"] for e in ev]
    assert len(set(seeds)) == len(seeds) and not (set(seeds) & set(range(100, 149))) and all(s < 1000 for s in seeds)
    lv = [e["surge_level"] for e in ev if e["scenario"] == "traffic_surge"]
    assert len(lv) == 10 and set(lv) == {25, 40}
    assert sum(1 for e in ev if e["scenario"] in p.HEALTHY) == 20
