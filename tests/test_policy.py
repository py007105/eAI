from eternalai import config, rulebook
from eternalai.policy import PolicyEngine

PLAN = rulebook.load(rulebook.DEFAULT_FILE, config.SERVICES)
V2 = rulebook.load(rulebook.RULEBOOK_DIR / "benchmark-v2.yaml", config.SERVICES)


def P(mode, **kw):
    kw.setdefault("rulebook", PLAN)
    kw.setdefault("kill_switch", False)
    kw.setdefault("protected", set(kw["rulebook"].protected_services))
    return PolicyEngine(mode, **kw)


def test_unlisted_runbook_blocked():
    assert P("autopilot").evaluate("rm_rf", "web").verdict == "blocked"


def test_unknown_target_blocked():
    assert P("autopilot").evaluate("restart_service", "database").verdict == "blocked"


def test_watch_only_never_executes():
    assert P("watch-only").evaluate("restart_service", "web").verdict == "observe_only"


def test_ask_first_needs_approval():
    assert P("ask-first").evaluate("restart_service", "web").verdict == "needs_approval"


def test_plan_mode_names_are_accepted():
    assert P("ask").mode == "ask-first" and P("watch").mode == "watch-only" and P("autopilot").mode == "autopilot"


def test_autopilot_executes_low_but_never_high():
    p = P("autopilot")
    assert p.evaluate("restart_service", "web").verdict == "execute"
    d = p.evaluate("rollback_release", "orders")
    assert d.verdict == "needs_approval" and d.risk == "high"


def test_plan_autopilot_runs_only_low():
    d = P("autopilot").evaluate("restart_service", "web", fault="error_spike")
    assert d.risk == "medium" and d.verdict == "needs_approval"


def test_plan_risk_table():
    p = P("autopilot")
    for s in config.SERVICES:
        assert p.risk("restart_service", s) == "low" and p.risk("clear_temp_path", s) == "low"
        assert p.risk("rollback_release", s) == "high"
        assert p.risk("recreate_container", s) == ("low" if s == "web" else "high")
        assert p.risk("restart_service", s, "latency_spike") == "medium"


def test_benchmark_v2_rulebook_reproduces_the_measured_policy():
    """benchmark-system-v2 policy.py: medium on orders/payments/inventory, low on web; autopilot executed low and medium."""
    p = P("autopilot", rulebook=V2)
    for s in config.SERVICES:
        for rb in ("recreate_container", "rollback_release"):
            assert p.risk(rb, s) == ("low" if s == "web" else "medium")
            assert p.evaluate(rb, s, now=1000.0).verdict == "execute"
    assert V2.cooldown_s == 90 and V2.max_actions_per_hour is None and V2.reproduces == "benchmark-system-v2"


def test_kill_switch_blocks_everything_and_returns_to_watch():
    p = P("autopilot", kill_switch=True)
    assert p.mode == "watch-only"
    for rb in ("restart_service", "clear_temp_path", "recreate_container", "rollback_release"):
        d = p.evaluate(rb, "web")
        assert d.verdict == "blocked" and "kill switch" in d.reason


def test_protected_service_needs_approval_in_every_acting_mode():
    for mode in ("ask-first", "autopilot"):
        assert P(mode, protected={"payments"}).evaluate("restart_service", "payments").verdict == "needs_approval"
    assert P("watch-only", protected={"payments"}).evaluate("restart_service", "payments").verdict == "observe_only"
    assert P("autopilot", protected={"payments"}).evaluate("restart_service", "web").verdict == "execute"


def test_defaults_come_from_config_and_rulebook(monkeypatch):
    monkeypatch.setattr(config, "KILL_SWITCH", True)
    monkeypatch.setattr(config, "PROTECTED_SERVICES", {"orders"})
    monkeypatch.setattr(config, "MODE", None)
    p = PolicyEngine(rulebook=PLAN)
    assert p.kill_switch is True and p.protected == {"orders", "payments"} and p.mode == "watch-only"


def test_mode_from_env_overrides_the_rulebook(monkeypatch):
    monkeypatch.setattr(config, "KILL_SWITCH", False)
    monkeypatch.setattr(config, "MODE", "autopilot")
    assert PolicyEngine(rulebook=PLAN).mode == "autopilot"
    monkeypatch.setattr(config, "MODE", None)
    assert PolicyEngine(rulebook=PLAN).mode == PLAN.mode == "ask-first"


def test_env_parsing():
    from eternalai.config import env_flag, env_list
    assert env_flag("true") and env_flag(" ON ") and env_flag("1") and not env_flag("") and not env_flag(None) and not env_flag("no")
    assert env_list("payments, inventory ,,") == {"payments", "inventory"} and env_list(None) == set()


def test_cooldown_then_breaker():
    p = P("autopilot")
    p.record_execution("web", now=1000.0)
    assert "cooldown" in p.evaluate("restart_service", "web", now=1010.0).reason
    assert p.evaluate("restart_service", "web", now=1000.0 + PLAN.cooldown_s + 1).verdict == "execute"
    p.record_execution("web", now=1200.0)
    d = p.evaluate("restart_service", "web", now=1400.0)
    assert d.verdict == "blocked" and "circuit breaker" in d.reason
    p.record_recovered("web")
    assert p.evaluate("restart_service", "web", now=1500.0).verdict == "execute"
