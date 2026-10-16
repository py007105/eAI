"""Verification: health checks plus a synthetic checkout through all four services, held over a window."""
from __future__ import annotations

import time
from dataclasses import dataclass

import httpx

from . import config


@dataclass
class Probe:
    ok: bool
    latency_s: float
    detail: str


def checkout_probe(client: httpx.Client, base=config.WEB_URL) -> Probe:
    """One sandbox checkout (web -> orders -> inventory + payments). Must return a confirmed order."""
    t0 = time.perf_counter()
    try:
        r = client.post(f"{base}/api/checkout", timeout=5,
                        json={"sku": "sku-mug", "qty": 1, "card": "4242424242424242"})
        ok = r.status_code == 200 and r.json().get("status") == "confirmed"
        return Probe(ok, time.perf_counter() - t0, f"HTTP {r.status_code}")
    except (httpx.HTTPError, ValueError) as e:
        return Probe(False, time.perf_counter() - t0, type(e).__name__)


def verify_recovery(observation_s: int = config.OBSERVATION_S, interval_s: float = 1.0,
                    latency_budget_s: float = 1.0) -> dict:
    """Run probes for `observation_s`. recovered = all pass in the window; partial = >=50%; else unresolved."""
    probes = []
    with httpx.Client() as c:
        end = time.time() + observation_s
        while time.time() < end:
            probes.append(checkout_probe(c))
            time.sleep(interval_s)
    n = len(probes)
    good = sum(p.ok and p.latency_s <= latency_budget_s for p in probes)
    rate = good / n if n else 0.0
    outcome = "recovered" if rate == 1.0 else ("partially_recovered" if rate >= 0.5 else "unresolved")
    return {"outcome": outcome, "probes": n, "success_rate": round(rate, 3),
            "p_max_latency_s": round(max((p.latency_s for p in probes), default=0), 3),
            "last_detail": probes[-1].detail if probes else "no probes"}
