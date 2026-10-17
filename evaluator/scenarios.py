"""Fault injection for the evaluator. Nothing here is importable by, or visible to, EternalAI.

Each scenario has: how to inject, the runtime label EternalAI should report (or None when it
should stay quiet / abstain), and whether it is a supported fault.
"""
from __future__ import annotations

import threading
import time

import docker
import httpx

SERVICES = ["web", "orders", "payments", "inventory"]
# scenario -> (expected runtime label, supported, targets allowed)
SCENARIOS = {
    "crash":        ("down",          True,  SERVICES),
    "latency":      ("latency_spike", True,  SERVICES),
    "error_spike":  ("error_spike",   True,  SERVICES),
    "memory_leak":  ("memory_leak",   True,  SERVICES),
    "disk_fill":    ("disk_fill",     True,  SERVICES),
    "bad_deploy":   ("bad_deploy",    True,  SERVICES),
    "cpu_burn":     ("unseen_fault",  False, SERVICES),   # no runbook, no label: EternalAI must abstain
    "traffic_surge": (None,           True,  ["web"]),    # healthy negative
    "good_deploy":  (None,            True,  SERVICES),   # healthy negative
}
HEALTHY_SCENARIOS = {"traffic_surge", "good_deploy"}


def strip_inherited(container_env, image_env, container_labels, image_labels):
    """Env and labels to pass when recreating a container from a DIFFERENT image.

    Env: only values set on the container itself, never ones the old image baked in (regression: a bad
    release image once ran with the old image's RELEASE_FLAVOR=good). Labels: drop values inherited from
    the old image but always keep compose labels, which identify the container (regression: stripping
    them left the new container invisible to lookups). Kept separate from EternalAI's copy on purpose."""
    env = [e for e in container_env if e not in (image_env or [])]
    labels = {k: v for k, v in container_labels.items()
              if k.startswith("com.docker.compose.") or (image_labels or {}).get(k) != v}
    return env, labels


class Injector:
    def __init__(self, chaos_token: str, web_url="http://web:8000"):
        self.d = docker.from_env()
        self.token = chaos_token
        self.web_url = web_url
        self._stop = threading.Event()
        self._threads: list[threading.Thread] = []

    # ------------------------------------------------------------ plumbing
    def _chaos(self, svc, kind, value=0):
        httpx.post(f"http://{svc}:8000/_chaos", json={"token": self.token, "kind": kind, "value": value}, timeout=5)

    def _container(self, svc):
        cs = self.d.containers.list(all=True, filters={"label": [f"com.docker.compose.service={svc}", "eai.managed=true"]})
        if len(cs) != 1:
            raise RuntimeError(f"expected 1 container for {svc}, found {len(cs)}")
        return cs[0]

    def _recreate(self, svc, image_ref):
        c = self._container(svc)
        a, hc = c.attrs, c.attrs["HostConfig"]
        net = next(iter(a["NetworkSettings"]["Networks"]))
        ports = {p: [int(b["HostPort"]) for b in bs][0] for p, bs in (hc.get("PortBindings") or {}).items()}
        host_cfg = self.d.api.create_host_config(binds=hc.get("Binds"), mem_limit=hc.get("Memory") or None,
                                                 port_bindings=ports or None)
        net_cfg = self.d.api.create_networking_config({net: self.d.api.create_endpoint_config(aliases=[svc])})
        name = c.name
        img = c.image.attrs["Config"]
        env, labels = strip_inherited(a["Config"]["Env"], img.get("Env"), a["Config"]["Labels"], img.get("Labels"))
        c.stop(timeout=5)
        c.remove()
        new = self.d.api.create_container(image_ref, name=name, environment=env,
                                          labels=labels, host_config=host_cfg,
                                          networking_config=net_cfg, ports=list(ports) or None)
        self.d.api.start(new["Id"])

    def _wait_healthy(self, svc, timeout=40):
        end = time.time() + timeout
        while time.time() < end:
            try:
                if httpx.get(f"http://{svc}:8000/healthz", timeout=2).status_code == 200:
                    return True
            except httpx.HTTPError:
                pass
            time.sleep(1)
        return False

    def _background(self, fn):
        t = threading.Thread(target=fn, daemon=True)
        t.start()
        self._threads.append(t)

    # ------------------------------------------------------------ scenarios
    def inject(self, scenario: str, svc: str, rng):
        """Introduce the fault. Returns the private parameters that are logged as ground truth."""
        if scenario == "crash":
            self._container(svc).kill()
            return {}
        if scenario == "latency":
            ms = rng.choice([600, 900, 1400])
            self._chaos(svc, "latency", ms)
            return {"latency_ms": ms}
        if scenario == "error_spike":
            p = rng.choice([0.4, 0.6, 0.8])
            self._chaos(svc, "errors", p)
            return {"error_rate": p}
        if scenario == "memory_leak":
            mb = rng.choice([4, 6, 8])
            # One call: the leak then runs INSIDE the service process, like a real leak, so a restart or recreate removes
            # it. (Training data was collected with the evaluator re-posting the leak every 2 s from outside; the first
            # seconds look the same. Docs record this change.)
            self._chaos(svc, "leak_stream", mb)
            return {"leak_mb_per_2s": mb, "mode": "in-process stream"}
        if scenario == "disk_fill":
            mb = rng.choice([15, 25, 35])
            # A runaway job inside the service dumps files for ~30 s and stops; the files stay until cleaned.
            self._chaos(svc, "disk_burst", mb)
            return {"fill_mb_per_2s": mb, "mode": "in-process 30 s burst"}
        if scenario == "bad_deploy":
            self._recreate(svc, f"eai/{svc}:v3-bad")
            return {"image": f"eai/{svc}:v3-bad"}
        if scenario == "good_deploy":
            self._recreate(svc, f"eai/{svc}:v2-good")
            return {"image": f"eai/{svc}:v2-good"}
        if scenario == "cpu_burn":
            self._chaos(svc, "cpu", 2)
            return {"threads": 2}
        if scenario == "traffic_surge":
            rps = rng.choice([25, 40])

            def surge():
                end = time.time() + 40
                with httpx.Client(limits=httpx.Limits(max_connections=100)) as c:
                    while time.time() < end and not self._stop.is_set():
                        try:
                            c.get(f"{self.web_url}/api/products", timeout=5)
                        except httpx.HTTPError:
                            pass
                        time.sleep(1 / rps)
            for _ in range(4):
                self._background(surge)
            return {"extra_rps_per_thread": rps}
        raise ValueError(scenario)

    def restore(self, dirty: set[str] | None = None):
        """Return the stack to its healthy baseline: v1 images, no chaos, all containers up.

        Services in `dirty` (touched by the last run) are always recreated from v1, which also
        clears leaked memory and scratch files; others only get a chaos reset."""
        self._stop.set()
        for t in self._threads:
            t.join(timeout=5)
        self._threads.clear()
        self._stop.clear()
        image_changed = False
        for svc in SERVICES:
            c = self._container(svc)
            c.reload()
            tag = c.attrs["Config"]["Image"]  # the reference it was created from (stable across rebuilds)
            if svc in (dirty or set()) or tag != f"eai/{svc}:v1":
                image_changed |= tag != f"eai/{svc}:v1"
                self._recreate(svc, f"eai/{svc}:v1")
            elif c.status != "running":
                c.start()
            self._wait_healthy(svc)
            try:
                self._chaos(svc, "reset")
            except httpx.HTTPError:
                pass
        return image_changed
