"""Shared observability and fault hooks for the four services.

Provides: JSON logs, Prometheus metrics, optional OpenTelemetry traces, a
/healthz and /metrics endpoint, and a token-protected /_chaos endpoint that the
independent evaluator uses to introduce faults. EternalAI never calls /_chaos.
"""
import json
import logging
import os
import random
import time
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Request, Response
from prometheus_client import (CONTENT_TYPE_LATEST, Counter, Gauge, Histogram,
                               generate_latest)

SERVICE = os.getenv("SERVICE", "unknown")
VERSION = os.getenv("APP_VERSION", "dev")
RELEASE = os.getenv("RELEASE_FLAVOR", "good")  # baked into the image at build time
CHAOS_TOKEN = os.getenv("CHAOS_TOKEN", "evaluator-only")
SCRATCH = Path(os.getenv("SCRATCH_DIR", "/tmp/eai-scratch"))

REQS = Counter("http_requests_total", "Requests", ["service", "route", "status"])
LAT = Histogram("http_request_duration_seconds", "Latency", ["service", "route"],
                buckets=(.005, .01, .025, .05, .1, .25, .5, 1, 2.5, 5, 10))
DEPS = Counter("dependency_calls_total", "Calls to other services",
               ["service", "target", "outcome"])
ERR_LOGS = Counter("error_logs_total", "Error-level log lines", ["service"])
MEM = Gauge("app_memory_bytes", "Memory used by the process (RSS)", ["service"])
MEM_LIMIT = Gauge("app_memory_limit_bytes", "Container memory limit (0 = none)", ["service"])
DISK_USED = Gauge("app_scratch_disk_bytes", "Bytes in the scratch directory", ["service"])
START = Gauge("app_start_time_seconds", "Process start time", ["service"])
INFO = Gauge("app_build_info", "Build info", ["service", "version", "release"])

SCRATCH_LIMIT = int(os.getenv("SCRATCH_LIMIT_MB", "300")) * 1024 * 1024  # "disk full" threshold

chaos = {"latency_ms": 0, "error_rate": 0.0, "leak": [], "cpu_burn": False}


def _burn():
    while chaos["cpu_burn"]:
        sum(i * i for i in range(20000))


class JsonFormatter(logging.Formatter):
    def format(self, r):
        if r.levelno >= logging.ERROR:
            ERR_LOGS.labels(SERVICE).inc()
        return json.dumps({"t": round(time.time(), 3), "service": SERVICE, "level": r.levelname,
                           "version": VERSION, "msg": r.getMessage()})


def _rss() -> int:
    try:
        for line in open("/proc/self/status"):
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) * 1024
    except OSError:
        pass
    return 0


def _mem_limit() -> int:
    for p in ("/sys/fs/cgroup/memory.max", "/sys/fs/cgroup/memory/memory.limit_in_bytes"):
        try:
            v = open(p).read().strip()
            return 0 if v == "max" else int(v)
        except OSError:
            continue
    return 0


def _scratch_bytes() -> int:
    return sum(f.stat().st_size for f in SCRATCH.glob("*") if f.is_file()) if SCRATCH.exists() else 0


def setup(app: FastAPI) -> logging.Logger:
    log = logging.getLogger(SERVICE)
    h = logging.StreamHandler()
    h.setFormatter(JsonFormatter())
    log.handlers[:] = [h]
    log.setLevel(logging.INFO)
    SCRATCH.mkdir(parents=True, exist_ok=True)
    START.labels(SERVICE).set(time.time())
    INFO.labels(SERVICE, VERSION, RELEASE).set(1)
    MEM_LIMIT.labels(SERVICE).set(_mem_limit())

    if os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"):
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        tp = TracerProvider(resource=Resource.create({"service.name": SERVICE,
                                                      "service.version": VERSION}))
        tp.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
        trace.set_tracer_provider(tp)
        FastAPIInstrumentor.instrument_app(app, excluded_urls="metrics,healthz")
        HTTPXClientInstrumentor().instrument()

    @app.middleware("http")
    async def observe(request: Request, call_next):
        route = request.url.path
        if route in ("/metrics", "/healthz") or route.startswith("/_chaos"):
            return await call_next(request)
        t0 = time.perf_counter()
        status = 500
        try:
            if chaos["latency_ms"]:
                import asyncio
                await asyncio.sleep(chaos["latency_ms"] / 1000)
            if _scratch_bytes() > SCRATCH_LIMIT:  # disk full: writes and reads of local state fail
                log.error("OSError: [Errno 28] No space left on device")
                status = 500
                return Response('{"detail":"no space left on device"}', 500, media_type="application/json")
            bad_release = RELEASE == "bad" and route != "/"
            if random.random() < max(chaos["error_rate"], 0.7 if bad_release else 0.0):
                log.error(f"injected failure on {route}")
                status = 500
                return Response('{"detail":"internal error"}', 500, media_type="application/json")
            resp = await call_next(request)
            status = resp.status_code
            return resp
        finally:
            REQS.labels(SERVICE, route, str(status)).inc()
            LAT.labels(SERVICE, route).observe(time.perf_counter() - t0)

    @app.get("/healthz")
    def healthz():
        return {"status": "ok", "service": SERVICE, "version": VERSION}

    @app.get("/metrics")
    def metrics():
        MEM.labels(SERVICE).set(_rss())
        DISK_USED.labels(SERVICE).set(_scratch_bytes())
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    @app.post("/_chaos")
    async def set_chaos(request: Request):
        body = await request.json()
        if body.get("token") != CHAOS_TOKEN:
            raise HTTPException(403, "forbidden")
        kind, val = body.get("kind"), body.get("value", 0)
        if kind == "latency":
            chaos["latency_ms"] = int(val)
        elif kind == "errors":
            chaos["error_rate"] = float(val)
        elif kind == "leak":  # allocate `val` MB and keep it
            chaos["leak"].append(bytearray(int(val) * 1024 * 1024))
        elif kind == "disk":  # write `val` MB into the scratch dir
            with open(SCRATCH / f"fill-{time.time_ns()}.bin", "wb") as f:
                f.write(os.urandom(1024 * 1024) * int(val))
        elif kind == "cpu":  # busy-loop threads (GIL-bound, so one core at most)
            import threading
            chaos["cpu_burn"] = True
            for _ in range(int(val) or 1):
                threading.Thread(target=_burn, daemon=True).start()
        elif kind == "reset":
            chaos.update(latency_ms=0, error_rate=0.0, leak=[], cpu_burn=False)
        else:
            raise HTTPException(400, "unknown kind")
        return {"ok": True, "kind": kind}

    return log


async def call(client: httpx.AsyncClient, target: str, method: str, url: str, **kw):
    """HTTP call to another service that records dependency outcomes."""
    try:
        r = await client.request(method, url, timeout=kw.pop("timeout", 3.0), **kw)
        DEPS.labels(SERVICE, target, "ok" if r.status_code < 500 else "error").inc()
        return r
    except httpx.HTTPError:
        DEPS.labels(SERVICE, target, "error").inc()
        raise
