"""Deterministic policy engine. The LLM never reaches this: it only proposes a runbook_id.

Decisions depend on mode, runbook risk, target, cooldown and a per-service circuit breaker.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from . import config

# runbook_id -> (risk, needs_target). Only runbooks that are really implemented in executor.py.
RUNBOOKS = {
    "restart_service": "low",
    "clear_temp_path": "low",
    "recreate_container": "medium",
    "rollback_release": "medium",
}
STATEFUL = {"orders", "payments", "inventory"}  # own a SQLite volume; data survives, but riskier


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

    def risk(self, runbook_id: str, service: str) -> str:
        r = RUNBOOKS[runbook_id]
        if r == "medium" and service in STATEFUL:
            return "medium"
        return "low" if r == "low" else ("low" if service == "web" else "medium")

    def evaluate(self, runbook_id: str, service: str, now: float | None = None) -> Decision:
        now = now or time.time()
        if runbook_id not in RUNBOOKS:
            return Decision("blocked", f"runbook '{runbook_id}' is not on the allow-list")
        if service not in config.SERVICES:
            return Decision("blocked", f"target '{service}' is not a managed service")
        risk = self.risk(runbook_id, service)
        acts = self.history.get(service, [])
        if service in self.breaker_open or len(acts) >= config.MAX_ACTIONS_PER_SERVICE:
            self.breaker_open.add(service)
            return Decision("blocked", f"circuit breaker open for {service}: "
                            f"{len(acts)} interventions without a verified recovery; escalate to a human", risk)
        if acts and now - acts[-1] < config.COOLDOWN_S:
            return Decision("blocked", f"cooldown: last action on {service} was {now - acts[-1]:.0f}s ago", risk)
        if self.mode == "watch-only":
            return Decision("observe_only", "watch-only mode: proposal recorded, nothing executed", risk)
        if self.mode == "autopilot" and risk in ("low", "medium"):
            return Decision("execute", f"autopilot: {risk}-risk runbook on allow-list", risk)
        return Decision("needs_approval", f"{self.mode}: {risk}-risk action requires approval", risk)

    def record_execution(self, service: str, now: float | None = None):
        self.history.setdefault(service, []).append(now or time.time())

    def record_recovered(self, service: str):
        """A verified recovery resets the intervention count and closes the breaker."""
        self.history.pop(service, None)
        self.breaker_open.discard(service)
