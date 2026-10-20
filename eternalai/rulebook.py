"""Rulebook: the company policy as a YAML file (plan §15.5), loaded once at start and validated.

    ETERNALAI_POLICY_FILE=eternalai/rulebooks/default.yaml        (default: the plan's values)
    ETERNALAI_POLICY_FILE=eternalai/rulebooks/benchmark-v2.yaml   (reproduces the system measured in benchmark v2)

An invalid file stops the brain at start with a message that names the field; it never falls back silently.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

RULEBOOK_DIR = Path(__file__).resolve().parent / "rulebooks"
DEFAULT_FILE = RULEBOOK_DIR / "default.yaml"

RISKS = ("low", "medium", "high")
MODE_ALIASES = {"watch": "watch-only", "watch-only": "watch-only", "ask": "ask-first", "ask-first": "ask-first",
                "autopilot": "autopilot"}
# Runbooks the executor really implements (eternalai/executor.py). A rulebook may not invent new ones.
KNOWN_RUNBOOKS = ("restart_service", "clear_temp_path", "recreate_container", "rollback_release")
FAULT_OVERRIDE_KEYS = {"risk", "action", "act_only_if_user_impact"}
TOP_KEYS = {"mode", "auto_allowed_risks", "protected_services", "database_services", "max_actions_per_hour", "cooldown_s",
            "max_unverified_actions_per_service", "namespaces", "runbook_risk", "service_risk", "fault_overrides",
            "reproduces"}


class RulebookError(ValueError):
    pass


def canonical_mode(mode: str) -> str:
    m = MODE_ALIASES.get(str(mode).strip().lower())
    if m is None:
        raise RulebookError(f"mode must be one of {sorted(MODE_ALIASES)}, got {mode!r}")
    return m


def risk_max(*risks: str) -> str:
    return max(risks, key=RISKS.index)


@dataclass(frozen=True)
class Rulebook:
    source: str
    mode: str
    auto_allowed_risks: tuple
    protected_services: frozenset
    database_services: frozenset
    max_actions_per_hour: int | None
    cooldown_s: float
    max_unverified_actions_per_service: int
    namespaces: tuple
    runbook_risk: dict
    service_risk: dict = field(default_factory=dict)
    fault_overrides: dict = field(default_factory=dict)
    reproduces: str | None = None

    def risk(self, runbook_id: str, service: str, fault: str | None = None) -> str:
        """Risk of the runbook on this service (a per-service entry replaces the base risk), then raised (never lowered) by a
        fault override, and always high on a database service."""
        r = self.service_risk.get(service, {}).get(runbook_id, self.runbook_risk[runbook_id])
        fo = self.fault_overrides.get(fault or "", {})
        if "risk" in fo:
            r = risk_max(r, fo["risk"])
        if service in self.database_services:
            r = "high"
        return r

    def summary(self) -> dict:
        return {"file": Path(self.source).name, "reproduces": self.reproduces, "auto_allowed_risks": list(self.auto_allowed_risks),
                "protected_services": sorted(self.protected_services), "database_services": sorted(self.database_services),
                "max_actions_per_hour": self.max_actions_per_hour, "cooldown_s": self.cooldown_s,
                "max_unverified_actions_per_service": self.max_unverified_actions_per_service,
                "namespaces": list(self.namespaces), "runbook_risk": dict(self.runbook_risk),
                "service_risk": {k: dict(v) for k, v in self.service_risk.items()},
                "fault_overrides": {k: dict(v) for k, v in self.fault_overrides.items()}}


def _risk(value, where: str) -> str:
    if value not in RISKS:
        raise RulebookError(f"{where}: risk must be one of {RISKS}, got {value!r}")
    return value


def _names(value, where: str) -> list:
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(v, str) and v.strip() for v in value):
        raise RulebookError(f"{where}: must be a list of names")
    return [v.strip() for v in value]


def parse(data, source: str = "<memory>", services: list | None = None) -> Rulebook:
    if not isinstance(data, dict):
        raise RulebookError(f"{source}: the rulebook must be a YAML mapping")
    unknown = set(data) - TOP_KEYS
    if unknown:
        raise RulebookError(f"{source}: unknown field(s) {sorted(unknown)}")
    for k in ("auto_allowed_risks", "cooldown_s", "max_unverified_actions_per_service", "runbook_risk"):
        if k not in data:
            raise RulebookError(f"{source}: missing required field '{k}'")
    known_services = set(services or [])

    auto = _names(data["auto_allowed_risks"], "auto_allowed_risks")
    for r in auto:
        _risk(r, "auto_allowed_risks")
    if "high" in auto:
        raise RulebookError("auto_allowed_risks: 'high' may never run without approval (plan §14)")

    rr = data["runbook_risk"]
    if not isinstance(rr, dict) or set(rr) != set(KNOWN_RUNBOOKS):
        raise RulebookError(f"runbook_risk: must give a risk for exactly these runbooks: {list(KNOWN_RUNBOOKS)}")
    runbook_risk = {k: _risk(v, f"runbook_risk.{k}") for k, v in rr.items()}

    service_risk = {}
    for svc, m in (data.get("service_risk") or {}).items():
        if known_services and svc not in known_services:
            raise RulebookError(f"service_risk: unknown service {svc!r}")
        if not isinstance(m, dict) or not set(m) <= set(KNOWN_RUNBOOKS):
            raise RulebookError(f"service_risk.{svc}: must map known runbooks to a risk")
        service_risk[svc] = {k: _risk(v, f"service_risk.{svc}.{k}") for k, v in m.items()}

    reproduces = data.get("reproduces")
    if reproduces is not None and (not isinstance(reproduces, str) or not reproduces.strip()):
        raise RulebookError("reproduces: must name the measured system (e.g. a git tag)")
    rollback = [runbook_risk["rollback_release"]] + [m["rollback_release"] for m in service_risk.values() if "rollback_release" in m]
    if any(r != "high" for r in rollback) and not reproduces:
        # The plan: rollback always needs approval. Only a file that reproduces an already-measured system may differ,
        # and it must say which one, so every number run under it can be labelled.
        raise RulebookError("rollback_release: must be 'high' on every service (plan §14) unless the file sets 'reproduces'")

    fault_overrides = {}
    for fault, m in (data.get("fault_overrides") or {}).items():
        if not isinstance(m, dict) or not set(m) <= FAULT_OVERRIDE_KEYS or not m:
            raise RulebookError(f"fault_overrides.{fault}: allowed keys are {sorted(FAULT_OVERRIDE_KEYS)}")
        if "risk" in m:
            _risk(m["risk"], f"fault_overrides.{fault}.risk")
        if "action" in m and m["action"] != "escalate":
            raise RulebookError(f"fault_overrides.{fault}.action: only 'escalate' is supported")
        if "act_only_if_user_impact" in m and not isinstance(m["act_only_if_user_impact"], bool):
            raise RulebookError(f"fault_overrides.{fault}.act_only_if_user_impact: must be true or false")
        fault_overrides[fault] = dict(m)

    cap = data.get("max_actions_per_hour")
    if cap is not None and (not isinstance(cap, int) or isinstance(cap, bool) or cap < 1):
        raise RulebookError("max_actions_per_hour: must be a positive integer or null")
    cd = data["cooldown_s"]
    if not isinstance(cd, (int, float)) or isinstance(cd, bool) or cd < 0:
        raise RulebookError("cooldown_s: must be a number >= 0")
    mu = data["max_unverified_actions_per_service"]
    if not isinstance(mu, int) or isinstance(mu, bool) or mu < 1:
        raise RulebookError("max_unverified_actions_per_service: must be an integer >= 1")

    protected = _names(data.get("protected_services"), "protected_services")
    databases = _names(data.get("database_services"), "database_services")
    for name, lst in (("protected_services", protected), ("database_services", databases)):
        bad = [s for s in lst if known_services and s not in known_services]
        if bad:
            # A name that matches no managed service would silently protect nothing.
            raise RulebookError(f"{name}: unknown service(s) {bad}")
    return Rulebook(source=str(source), mode=canonical_mode(data.get("mode", "ask-first")), auto_allowed_risks=tuple(auto),
                    protected_services=frozenset(protected), database_services=frozenset(databases),
                    max_actions_per_hour=cap, cooldown_s=float(cd), max_unverified_actions_per_service=mu,
                    namespaces=tuple(_names(data.get("namespaces"), "namespaces")), runbook_risk=runbook_risk,
                    service_risk=service_risk, fault_overrides=fault_overrides,
                    reproduces=reproduces.strip() if reproduces else None)


def policy_file() -> Path:
    """ETERNALAI_POLICY_FILE (or the plan's name POLICY_FILE); a bare name is looked up in eternalai/rulebooks/."""
    p = os.getenv("ETERNALAI_POLICY_FILE") or os.getenv("POLICY_FILE") or ""
    if not p.strip():
        return DEFAULT_FILE
    path = Path(p.strip())
    if not path.is_absolute() and not path.exists() and (RULEBOOK_DIR / path.name).exists():
        path = RULEBOOK_DIR / path.name
    return path


def load(path: str | Path | None = None, services: list | None = None) -> Rulebook:
    path = Path(path) if path else policy_file()
    if not path.exists():
        raise RulebookError(f"policy file not found: {path}")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        raise RulebookError(f"{path.name}: not valid YAML ({e.__class__.__name__})") from e
    return parse(data, str(path), services)
