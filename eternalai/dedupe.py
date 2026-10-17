"""Two small pieces of alert hygiene, kept pure so they can be unit-tested.

ReleaseGrace: a normal rolling release restarts the service for a few seconds (not scraped, callers erroring). The live smoke
test showed such a blip opening an incident on a healthy `good_deploy`. After a release change becomes visible
(`deploys_3m` rises) anomalies on that service are ignored for `grace_s`; a BAD release still opens an incident once its errors
persist past the grace period. Cost: bad-deploy detection is up to `grace_s` slower.

Suppressor: after an incident ends without a verified recovery (escalated, unresolved, partially recovered), the same ongoing
anomaly must not open a new incident every few seconds. The service stays suppressed until it has been quiet for `quiet_ticks`.
"""
from __future__ import annotations

UNRESOLVED = ("escalated", "unresolved", "partially_recovered")


class ReleaseGrace:
    def __init__(self, grace_s: float = 15.0):
        self.grace_s, self.last_seen_at, self.last_value = grace_s, {}, {}

    def in_grace(self, service: str, deploys_3m: float | None, now: float) -> bool:
        dep = deploys_3m or 0.0
        if dep > self.last_value.get(service, 0.0):          # a new release change just became visible
            self.last_seen_at[service] = now
        self.last_value[service] = dep
        t = self.last_seen_at.get(service)
        return t is not None and now - t < self.grace_s


class Suppressor:
    def __init__(self, quiet_ticks: int = 5):
        self.quiet_ticks, self.suppressed, self.quiet = quiet_ticks, set(), {}

    def note_incident(self, status: str, services) -> None:
        if status in UNRESOLVED:
            self.suppressed |= set(services)
            for s in services:
                self.quiet[s] = 0

    def update(self, anomalous: dict) -> None:
        for s in list(self.suppressed):
            self.quiet[s] = 0 if anomalous.get(s) else self.quiet.get(s, 0) + 1
            if self.quiet[s] >= self.quiet_ticks:
                self.suppressed.discard(s)

    def filter(self, confirmed: set) -> set:
        return set(confirmed) - self.suppressed
