"""Rulebook YAML: the shipped files load; every invalid field is refused with a message naming it."""
import copy

import pytest
import yaml

from engine import config, rulebook
from engine.rulebook import RulebookError, parse

S = list(config.SERVICES)
BASE = yaml.safe_load(rulebook.DEFAULT_FILE.read_text(encoding="utf-8"))


def with_(**changes):
    d = copy.deepcopy(BASE)
    for k, v in changes.items():
        if v is None and k in d:
            del d[k]
        else:
            d[k] = v
    return d


def test_shipped_rulebooks_load():
    plan = rulebook.load(rulebook.DEFAULT_FILE, S)
    assert plan.auto_allowed_risks == ("low",) and plan.protected_services == {"payments"} and plan.cooldown_s == 40
    assert plan.max_actions_per_hour == 10 and plan.runbook_risk["rollback_release"] == "high" and plan.reproduces is None
    v2 = rulebook.load(rulebook.RULEBOOK_DIR / "benchmark-v2.yaml", S)
    assert v2.auto_allowed_risks == ("low", "medium") and v2.reproduces == "benchmark-system-v2"


@pytest.mark.parametrize("data, field", [
    (with_(auto_allowed_risks=["low", "high"]), "auto_allowed_risks"),
    (with_(auto_allowed_risks=["urgent"]), "auto_allowed_risks"),
    (with_(cooldown_s=-1), "cooldown_s"),
    (with_(cooldown_s=None), "cooldown_s"),
    (with_(max_actions_per_hour=0), "max_actions_per_hour"),
    (with_(max_actions_per_hour="ten"), "max_actions_per_hour"),
    (with_(max_unverified_actions_per_service=0), "max_unverified_actions_per_service"),
    (with_(mode="yolo"), "mode"),
    (with_(protected_services=["paymnts"]), "protected_services"),
    (with_(database_services=["postgres"]), "database_services"),
    (with_(runbook_risk={"restart_service": "low"}), "runbook_risk"),
    (with_(runbook_risk={**BASE["runbook_risk"], "rollback_release": "low"}), "rollback_release"),
    (with_(service_risk={"web": {"rollback_release": "medium"}}), "rollback_release"),
    (with_(service_risk={"nosuch": {"restart_service": "low"}}), "service_risk"),
    (with_(fault_overrides={"x": {"action": "restart"}}), "fault_overrides"),
    (with_(fault_overrides={"x": {"colour": "red"}}), "fault_overrides"),
    (with_(extra_field=1), "unknown field"),
    ("just a string", "mapping"),
])
def test_invalid_rulebooks_are_refused(data, field):
    with pytest.raises(RulebookError, match=field):
        parse(data, "test.yaml", S)


def test_lowering_rollback_needs_an_explicit_reproduction_label():
    d = with_(runbook_risk={**BASE["runbook_risk"], "rollback_release": "medium"}, reproduces="benchmark-system-v2")
    assert parse(d, "x.yaml", S).risk("rollback_release", "orders") == "medium"


def test_database_targets_are_always_high_risk():
    rb = parse(with_(database_services=["inventory"]), "x.yaml", S)
    assert rb.risk("restart_service", "inventory") == "high" and rb.risk("restart_service", "web") == "low"


def test_fault_override_raises_but_never_lowers():
    rb = parse(with_(fault_overrides={"bad_deploy": {"risk": "low"}, "error_spike": {"risk": "medium"}}), "x.yaml", S)
    assert rb.risk("rollback_release", "web", "bad_deploy") == "high"
    assert rb.risk("restart_service", "web", "error_spike") == "medium"


def test_missing_or_broken_file(tmp_path):
    with pytest.raises(RulebookError, match="not found"):
        rulebook.load(tmp_path / "none.yaml", S)
    bad = tmp_path / "bad.yaml"
    bad.write_text("mode: [unclosed", encoding="utf-8")
    with pytest.raises(RulebookError, match="not valid YAML"):
        rulebook.load(bad, S)


def test_policy_file_env(monkeypatch):
    monkeypatch.delenv("POLICY_FILE", raising=False)
    monkeypatch.setenv("ETERNALAI_POLICY_FILE", "benchmark-v2.yaml")       # a bare name is looked up in engine/rulebooks/
    assert rulebook.policy_file() == rulebook.RULEBOOK_DIR / "benchmark-v2.yaml"
    monkeypatch.delenv("ETERNALAI_POLICY_FILE")
    monkeypatch.setenv("POLICY_FILE", "benchmark-v2.yaml")                 # the plan's variable name
    assert rulebook.policy_file().name == "benchmark-v2.yaml"
    monkeypatch.delenv("POLICY_FILE")
    assert rulebook.policy_file() == rulebook.DEFAULT_FILE
