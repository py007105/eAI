from eternalai.policy import PolicyEngine


def test_unlisted_runbook_blocked():
    assert PolicyEngine("autopilot").evaluate("rm_rf", "web").verdict == "blocked"


def test_unknown_target_blocked():
    assert PolicyEngine("autopilot").evaluate("restart_service", "database").verdict == "blocked"


def test_watch_only_never_executes():
    assert PolicyEngine("watch-only").evaluate("restart_service", "web").verdict == "observe_only"


def test_ask_first_needs_approval():
    assert PolicyEngine("ask-first").evaluate("restart_service", "web").verdict == "needs_approval"


def test_autopilot_executes_low_and_medium():
    p = PolicyEngine("autopilot")
    assert p.evaluate("restart_service", "web").verdict == "execute"
    assert p.evaluate("rollback_release", "orders").verdict == "execute"


def test_cooldown_then_breaker():
    p = PolicyEngine("autopilot")
    p.record_execution("web", now=1000.0)
    assert "cooldown" in p.evaluate("restart_service", "web", now=1010.0).reason
    p.record_execution("web", now=1200.0)
    d = p.evaluate("restart_service", "web", now=1400.0)
    assert d.verdict == "blocked" and "circuit breaker" in d.reason
    p.record_recovered("web")
    assert p.evaluate("restart_service", "web", now=1500.0).verdict == "execute"
