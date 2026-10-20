from eternalai.policy import PolicyEngine


def test_unlisted_runbook_blocked():
    assert PolicyEngine("autopilot").evaluate("rm_rf", "web").verdict == "blocked"


def test_unknown_target_blocked():
    assert PolicyEngine("autopilot").evaluate("restart_service", "database").verdict == "blocked"


def test_watch_only_never_executes():
    assert PolicyEngine("watch-only").evaluate("restart_service", "web").verdict == "observe_only"


def test_ask_first_needs_approval():
    assert PolicyEngine("ask-first").evaluate("restart_service", "web").verdict == "needs_approval"


def test_autopilot_executes_low_but_never_high():
    p = PolicyEngine("autopilot")
    assert p.evaluate("restart_service", "web").verdict == "execute"
    d = p.evaluate("rollback_release", "orders")
    assert d.verdict == "needs_approval" and d.risk == "high"


def test_risk_table():
    p = PolicyEngine("autopilot")
    for s in ("web", "orders", "payments", "inventory"):
        assert p.risk("restart_service", s) == "low" and p.risk("clear_temp_path", s) == "low"
        assert p.risk("rollback_release", s) == "high"
        assert p.risk("recreate_container", s) == ("low" if s == "web" else "high")


def test_kill_switch_blocks_everything():
    p = PolicyEngine("autopilot", kill_switch=True)
    for rb in ("restart_service", "clear_temp_path", "recreate_container", "rollback_release"):
        d = p.evaluate(rb, "web")
        assert d.verdict == "blocked" and "kill switch" in d.reason


def test_protected_service_is_observe_only_in_every_mode():
    for mode in ("watch-only", "ask-first", "autopilot"):
        p = PolicyEngine(mode, protected={"payments"})
        assert p.evaluate("restart_service", "payments").verdict == "observe_only"
    assert PolicyEngine("autopilot", protected={"payments"}).evaluate("restart_service", "web").verdict == "execute"


def test_defaults_come_from_config(monkeypatch):
    from eternalai import config
    monkeypatch.setattr(config, "KILL_SWITCH", True)
    monkeypatch.setattr(config, "PROTECTED_SERVICES", {"payments"})
    p = PolicyEngine("autopilot")
    assert p.kill_switch is True and p.protected == {"payments"}


def test_env_parsing():
    from eternalai.config import env_flag, env_list
    assert env_flag("true") and env_flag(" ON ") and env_flag("1") and not env_flag("") and not env_flag(None) and not env_flag("no")
    assert env_list("payments, inventory ,,") == {"payments", "inventory"} and env_list(None) == set()


def test_cooldown_then_breaker():
    p = PolicyEngine("autopilot")
    p.record_execution("web", now=1000.0)
    assert "cooldown" in p.evaluate("restart_service", "web", now=1010.0).reason
    p.record_execution("web", now=1200.0)
    d = p.evaluate("restart_service", "web", now=1400.0)
    assert d.verdict == "blocked" and "circuit breaker" in d.reason
    p.record_recovered("web")
    assert p.evaluate("restart_service", "web", now=1500.0).verdict == "execute"
