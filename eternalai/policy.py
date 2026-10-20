"""Deterministic policy engine. The LLM never reaches this: it only proposes a runbook_id.

Decisions depend on the kill switch, protected services, mode, runbook risk, target, cooldown and a per-service circuit
breaker. High-risk actions are never executed automatically: in every mode they need a human approval.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from . import config

# runbook_id -> base risk. Only runbooks that are really implemented in executor.py.
RUNBOOKS = {
    "restart_service": "low",
    "clear_temp_path": "low",
    "recreate_container": "medium",   # high on a stateful service, low on the stateless web service (see risk())
    "rollback_release": "high",       # a release change is high risk on every service
}
STATEFUL = {"orders", "payments", "inventory"}  # own a SQLite volume; data survives, but riskier
AUTO_RISKS = ("low", "medium")                   # what autopilot may execute without approval; never "high"


@dataclass
class Decision:
    verdict: str   # execute | needs_approval | blocked | observe_only
    reason: str
    risk: str = "low"


@dataclass
class PolicyEngine:
    mode: str = config.MODE
    history: dict = field(default_factory=dict)  # service -> [timestamps of executed actions]
    breaker_open: set = field(default_factory=set)
    kill_switch: bool = field(default_factory=lambda: config.KILL_SWITCH)
    protected: set = field(default_factory=lambda: set(config.PROTECTED_SERVICES))

    def risk(self, runbook_id: str, service: str) -> str:
        r = RUNBOOKS[runbook_id]
        if r == "medium":
            return "high" if service in STATEFUL else "low"
        return r

    def evaluate(self, runbook_id: str, service: str, now: float | None = None) -> Decision:
        now = now or time.time()
        if runbook_id not in RUNBOOKS:
            return Decision("blocked", f"runbook '{runbook_id}' is not on the allow-list")
        if service not in config.SERVICES:
            return Decision("blocked", f"target '{service}' is not a managed service")
        risk = self.risk(runbook_id, service)
        if self.kill_switch:
            return Decision("blocked", "kill switch is on: nothing is executed", risk)
        if service in self.protected:
            return Decision("observe_only", f"{service} is a protected service: proposal recorded, nothing executed", risk)
        acts = self.history.get(service, [])
        if service in self.breaker_open or len(acts) >= config.MAX_ACTIONS_PER_SERVICE:
            self.breaker_open.add(service)
            return Decision("blocked", f"circuit breaker open for {service}: "
                            f"{len(acts)} interventions without a verified recovery; escalate to a human", risk)
        if acts and now - acts[-1] < config.COOLDOWN_S:
            return Decision("blocked", f"cooldown: last action on {service} was {now - acts[-1]:.0f}s ago", risk)
        if self.mode == "watch-only":
            return Decision("observe_only", "watch-only mode: proposal recorded, nothing executed", risk)
        if self.mode == "autopilot" and risk in AUTO_RISKS:
            return Decision("execute", f"autopilot: {risk}-risk runbook on allow-list", risk)
        if risk == "high":
            return Decision("needs_approval", f"{self.mode}: high-risk action always requires approval", risk)
        return Decision("needs_approval", f"{self.mode}: {risk}-risk action requires approval", risk)

    def record_execution(self, service: str, now: float | None = None):
        self.history.setdefault(service, []).append(now or time.time())

    def record_recovered(self, service: str):
        """A verified recovery resets the intervention count and closes the breaker."""
        self.history.pop(service, None)
        self.breaker_open.discard(service)
