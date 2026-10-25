"""Deterministic policy engine. The LLM never reaches this: it only proposes a runbook_id.

The rules come from the rulebook YAML (engine/rulebook.py, plan §15.5). Decision order:
allow-list -> target -> kill switch -> fault override "escalate" -> circuit breaker -> cooldown -> hourly cap -> watch-only
-> unusual combination (approval) -> "act only if users are affected" -> protected service (approval) -> autopilot with an allowed risk (execute) -> approval.
High-risk actions are never executed automatically: the loader refuses "high" in auto_allowed_risks.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from . import config, rulebook as rb_mod
from .rulebook import KNOWN_RUNBOOKS, Rulebook

RUNBOOKS = KNOWN_RUNBOOKS   # the allow-list: only runbooks really implemented in executor.py
HOUR_S = 3600.0


@dataclass
class Decision:
    verdict: str   # execute | needs_approval | blocked | observe_only
    reason: str
    risk: str = "low"


def _load_default() -> Rulebook:
    return rb_mod.load(services=config.SERVICES)


@dataclass
class PolicyEngine:
    mode: str | None = None              # None: ETERNALAI_MODE if set, else the rulebook's mode
    rulebook: Rulebook = field(default_factory=_load_default)
    history: dict = field(default_factory=dict)  # service -> [timestamps of executed actions since the last verified recovery]
    breaker_open: set = field(default_factory=set)
    kill_switch: bool = field(default_factory=lambda: config.KILL_SWITCH)
    protected: set | None = None         # None: rulebook protected_services plus ETERNALAI_PROTECTED_SERVICES
    executed: list = field(default_factory=list)  # timestamps of every executed action (hourly cap)

    def __post_init__(self):
        self.mode = rb_mod.canonical_mode(self.mode or config.MODE or self.rulebook.mode)
        if self.protected is None:
            self.protected = set(self.rulebook.protected_services) | set(config.PROTECTED_SERVICES)
        if self.kill_switch:
            self.mode = "watch-only"     # plan §14: the kill switch returns everything to Watch mode

    def set_kill_switch(self, on: bool):
        self.kill_switch = bool(on)
        if self.kill_switch:
            self.mode = "watch-only"

    def risk(self, runbook_id: str, service: str, fault: str | None = None) -> str:
        return self.rulebook.risk(runbook_id, service, fault)

    def actions_last_hour(self, now: float) -> int:
        return sum(1 for t in self.executed if now - t < HOUR_S)

    def evaluate(self, runbook_id: str, service: str, now: float | None = None, fault: str | None = None,
                 user_impact: bool | None = None, unusual: bool = False) -> Decision:
        now = now or time.time()
        rb = self.rulebook
        if runbook_id not in RUNBOOKS:
            return Decision("blocked", f"runbook '{runbook_id}' is not on the allow-list")
        if service not in config.SERVICES:
            return Decision("blocked", f"target '{service}' is not a managed service")
        risk = self.risk(runbook_id, service, fault)
        if self.kill_switch:
            return Decision("blocked", "kill switch is on: nothing is executed", risk)
        fo = rb.fault_overrides.get(fault or "", {})
        if fo.get("action") == "escalate":
            return Decision("blocked", f"rulebook: {fault} is always escalated to a human", risk)
        acts = self.history.get(service, [])
        if service in self.breaker_open or len(acts) >= rb.max_unverified_actions_per_service:
            self.breaker_open.add(service)
            return Decision("blocked", f"circuit breaker open for {service}: "
                            f"{len(acts)} interventions without a verified recovery; escalate to a human", risk)
        if acts and now - acts[-1] < rb.cooldown_s:
            return Decision("blocked", f"cooldown: last action on {service} was {now - acts[-1]:.0f}s ago", risk)
        if rb.max_actions_per_hour is not None and self.actions_last_hour(now) >= rb.max_actions_per_hour:
            return Decision("blocked", f"hourly cap: {rb.max_actions_per_hour} actions already executed in the last hour", risk)
        if self.mode == "watch-only":
            return Decision("observe_only", "watch-only mode: proposal recorded, nothing executed", risk)
        if unusual:   # plan §9.1: only the joint score is abnormal, no single signal explains it -> never automatic
            return Decision("needs_approval", "unusual combination: only the joint anomaly score is high and no single signal "
                            "explains it, so nothing runs automatically", risk)
        if fo.get("act_only_if_user_impact") and user_impact is False:
            return Decision("observe_only", f"rulebook: {fault} is acted on only when users are affected; they are not", risk)
        if service in self.protected:
            return Decision("needs_approval", f"{service} is a protected service: every action needs approval", risk)
        if self.mode == "autopilot" and risk in rb.auto_allowed_risks:
            return Decision("execute", f"autopilot: {risk}-risk runbook allowed by the rulebook", risk)
        if risk == "high":
            return Decision("needs_approval", f"{self.mode}: high-risk action always requires approval", risk)
        return Decision("needs_approval", f"{self.mode}: {risk}-risk action requires approval", risk)

    def record_execution(self, service: str, now: float | None = None):
        t = now or time.time()
        self.history.setdefault(service, []).append(t)
        self.executed = [x for x in self.executed if t - x < HOUR_S] + [t]

    def record_recovered(self, service: str):
        """A verified recovery resets the intervention count and closes the breaker (not the hourly cap)."""
        self.history.pop(service, None)
        self.breaker_open.discard(service)
