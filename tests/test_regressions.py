"""Regression tests for bugs found while building the live stack. None of these need Docker."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "evaluator"))
sys.path.insert(0, str(ROOT / "ml" / "models"))

import scenarios as ev_scenarios  # noqa: E402
from collect_runs import SCENARIOS, scenario_order  # noqa: E402
from timing import DEPLOY_SETTLE_S, NORMAL_SETTLE_S, settle_seconds  # noqa: E402

from engine.executor import strip_inherited  # noqa: E402
from engine.features.window import fit_baseline, window_features  # noqa: E402

OLD_IMAGE_ENV = ["PATH=/usr/bin", "RELEASE_FLAVOR=good", "APP_VERSION=v1", "RELEASE_SEQ=1"]
CONTAINER_ENV = OLD_IMAGE_ENV + ["CHAOS_TOKEN=evaluator-only", "OTEL_EXPORTER_OTLP_ENDPOINT=http://jaeger:4318"]
OLD_IMAGE_LABELS = {"com.docker.compose.service": "inventory", "com.docker.compose.project": "eai",
                    "eai.service": "inventory", "eai.version": "v1", "eai.release_seq": "1"}
CONTAINER_LABELS = {**OLD_IMAGE_LABELS, "eai.managed": "true", "com.docker.compose.container-number": "1"}


# ---- bug 1: the old image's baked-in env overrode the new image (bad release ran as "good")
def test_old_image_env_is_not_carried_over():
    for fn in (strip_inherited, ev_scenarios.strip_inherited):
        env, _ = fn(CONTAINER_ENV, OLD_IMAGE_ENV, CONTAINER_LABELS, OLD_IMAGE_LABELS)
        assert "RELEASE_FLAVOR=good" not in env and "APP_VERSION=v1" not in env and "RELEASE_SEQ=1" not in env
        assert "CHAOS_TOKEN=evaluator-only" in env  # container-level settings are kept


# ---- bug 2: stripping inherited labels made the recreated container invisible to compose-label lookups
def test_compose_labels_survive_even_when_image_has_same_value():
    for fn in (strip_inherited, ev_scenarios.strip_inherited):
        _, labels = fn(CONTAINER_ENV, OLD_IMAGE_ENV, CONTAINER_LABELS, OLD_IMAGE_LABELS)
        assert labels["com.docker.compose.service"] == "inventory"
        assert labels["com.docker.compose.project"] == "eai"
        assert labels["eai.managed"] == "true"
        assert "eai.version" not in labels and "eai.release_seq" not in labels  # image-owned, must not stick


# ---- bug 3: restore noise (releases/restarts from the previous run) leaking into the next run
def test_settle_waits_out_the_deploy_signal():
    assert settle_seconds(False, False) == NORMAL_SETTLE_S
    assert settle_seconds(True, False) == DEPLOY_SETTLE_S == settle_seconds(False, True)
    assert DEPLOY_SETTLE_S > 180  # longer than the 3-minute deploys_3m lookback


def test_run_order_is_shuffled_and_not_fixed_across_repetitions():
    orders = [tuple(s for _, s in scenario_order(r, SCENARIOS)) for r in range(8)]
    assert all(sorted(o) == sorted(SCENARIOS) for o in orders)  # every scenario once per repetition
    assert len(set(orders)) > 1                                    # not the same order each time
    # a scenario must not always follow the same predecessor
    follows = {}
    for o in orders:
        for a, b in zip(o, o[1:]):
            follows.setdefault(b, set()).add(a)
    assert max(len(v) for v in follows.values()) > 1


def test_restart_feature_is_a_windowed_delta_not_a_level():
    """A restart from the previous run's restore sits in the 3-minute counter; it must not look like a new restart."""
    t = np.arange(0, 200, 2.0)
    base = pd.DataFrame({"req_rate": 10.0, "err_rate": 0.0, "p95_s": 0.05, "cpu_cores": 0.1, "up": 1.0,
                         "mem_bytes": 1e8, "mem_limit_bytes": 2.5e8}, index=t)
    stale = base.assign(restarts_3m=3.0)                                   # constant: old restarts only
    fresh = base.assign(restarts_3m=np.where(t < 180, 3.0, 4.0))           # one restart inside the window
    b = fit_baseline(base)
    assert window_features(stale, b)["restarts_in_window"] == 0.0
    assert window_features(fresh, b)["restarts_in_window"] == 1.0
