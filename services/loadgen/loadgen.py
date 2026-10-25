"""Continuous browsing and sandbox-checkout traffic with healthy surges.

Env: TARGET_URL, BASE_RPS (default 6), SURGE_EVERY_S (0 disables surges),
SURGE_FACTOR, SURGE_LEN_S, SEED. Metrics on :9100 (client-side view of failures).
"""
import asyncio
import os
import random
import time

import httpx
from prometheus_client import Counter, Gauge, Histogram, start_http_server

TARGET = os.getenv("TARGET_URL", "http://web:8000")
BASE_RPS = float(os.getenv("BASE_RPS", "6"))
SURGE_EVERY = float(os.getenv("SURGE_EVERY_S", "0"))
SURGE_FACTOR = float(os.getenv("SURGE_FACTOR", "4"))
SURGE_LEN = float(os.getenv("SURGE_LEN_S", "20"))
CHECKOUT_SHARE = 0.3
SKUS = ["sku-lamp", "sku-mug", "sku-bag", "sku-book"]

REQS = Counter("loadgen_requests_total", "Requests sent", ["kind", "outcome"])
LAT = Histogram("loadgen_latency_seconds", "Client latency", ["kind"],
                buckets=(.01, .025, .05, .1, .25, .5, 1, 2.5, 5, 10))
RPS = Gauge("loadgen_target_rps", "Current target request rate")


async def one(client: httpx.AsyncClient, rnd: random.Random):
    kind = "checkout" if rnd.random() < CHECKOUT_SHARE else "browse"
    t0 = time.perf_counter()
    try:
        if kind == "checkout":
            r = await client.post(f"{TARGET}/api/checkout", timeout=6,
                                  json={"sku": rnd.choice(SKUS), "qty": rnd.randint(1, 3),
                                        "card": "4242424242424242"})
        else:
            r = await client.get(f"{TARGET}/api/products", timeout=6)
        outcome = "ok" if r.status_code == 200 else "error"
    except httpx.HTTPError:
        outcome = "error"
    LAT.labels(kind).observe(time.perf_counter() - t0)
    REQS.labels(kind, outcome).inc()


async def main():
    start_http_server(9100)
    rnd = random.Random(int(os.getenv("SEED", "7")))
    t_start = time.time()
    async with httpx.AsyncClient(limits=httpx.Limits(max_connections=200)) as client:
        while True:
            now = time.time() - t_start
            surging = SURGE_EVERY > 0 and (now % SURGE_EVERY) < SURGE_LEN and now > SURGE_EVERY / 2
            rps = BASE_RPS * (SURGE_FACTOR if surging else 1)
            RPS.set(rps)
            asyncio.create_task(one(client, rnd))
            await asyncio.sleep(rnd.expovariate(rps))  # Poisson arrivals


if __name__ == "__main__":
    asyncio.run(main())
