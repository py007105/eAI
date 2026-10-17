"""Recovery runbooks implemented with the Docker SDK. Every action is audited.

Only four runbooks exist, all real:
  restart_service      restart the container in place
  recreate_container   remove and recreate the container from its current image (clears leaked state)
  rollback_release     recreate from the previous release image (lower eai.release_seq)
  clear_temp_path      delete files matching a fixed pattern in the approved temp path only

The target and arguments are fixed argv lists; nothing from an LLM or a user string is ever
passed to a shell.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import docker

from . import config

AUDIT_PATH = Path("runtime/audit.jsonl")


class ExecutionError(Exception):
    pass


def strip_inherited(container_env, image_env, container_labels, image_labels):
    """What to pass when recreating a container from a DIFFERENT image.

    Env: only values set on the container itself; values the old image baked in must not override the
    new image's own (regression: a "bad" release image once ran with the old image's RELEASE_FLAVOR=good).
    Labels: drop values inherited from the old image, but always keep compose labels, which identify the
    container (regression: stripping them left the new container invisible to lookups)."""
    env = [e for e in container_env if e not in (image_env or [])]
    labels = {k: v for k, v in container_labels.items()
              if k.startswith("com.docker.compose.") or (image_labels or {}).get(k) != v}
    return env, labels


class Executor:
    def __init__(self, client: docker.DockerClient | None = None):
        self.client = client or docker.from_env()
        self.audit: list[dict] = []
        AUDIT_PATH.parent.mkdir(exist_ok=True)

    # ---------------------------------------------------------------- helpers
    def _container(self, service):
        cs = self.client.containers.list(all=True, filters={
            "label": [f"com.docker.compose.service={service}", "eai.managed=true"]})
        if len(cs) != 1:
            raise ExecutionError(f"expected exactly one container for {service}, found {len(cs)}")
        return cs[0]

    def _log(self, **kw):
        rec = {"t": time.time(), **kw}
        self.audit.append(rec)
        with AUDIT_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
        return rec

    def _recreate_from(self, c, image_ref: str):
        """Replace container `c` by one from `image_ref` with the same name, network alias, env, volumes, limits, ports."""
        a, hc = c.attrs, c.attrs["HostConfig"]
        net = next(iter(a["NetworkSettings"]["Networks"]))
        svc = c.labels["com.docker.compose.service"]
        ports = {p: [int(b["HostPort"]) for b in bs][0] for p, bs in (hc.get("PortBindings") or {}).items()}
        host_cfg = self.client.api.create_host_config(
            binds=hc.get("Binds"), mem_limit=hc.get("Memory") or None,
            port_bindings=ports or None, restart_policy=hc.get("RestartPolicy") or None)
        net_cfg = self.client.api.create_networking_config(
            {net: self.client.api.create_endpoint_config(aliases=[svc])})
        name = c.name
        img = c.image.attrs["Config"]
        env, labels = strip_inherited(a["Config"]["Env"], img.get("Env"), a["Config"]["Labels"], img.get("Labels"))
        c.stop(timeout=5)
        c.remove()
        new = self.client.api.create_container(
            image_ref, name=name, environment=env, labels=labels,
            host_config=host_cfg, networking_config=net_cfg, ports=list(ports) or None)
        self.client.api.start(new["Id"])
        return new["Id"][:12]

    def _previous_release(self, service, current_seq):
        imgs = self.client.images.list(filters={"label": f"eai.service={service}"})
        cands = [(int(i.labels["eai.release_seq"]), i.tags[0]) for i in imgs
                 if i.tags and int(i.labels.get("eai.release_seq", 0)) < current_seq]
        if not cands:
            raise ExecutionError(f"no earlier release image for {service}")
        return max(cands)[1]

    # ---------------------------------------------------------------- runbooks
    def restart_service(self, service):
        c = self._container(service)
        c.restart(timeout=5)
        return {"restarted": service}

    def recreate_container(self, service):
        c = self._container(service)
        image = c.attrs["Config"]["Image"]
        return {"recreated": service, "image": image, "container": self._recreate_from(c, image)}

    def rollback_release(self, service):
        c = self._container(service)
        cur = int(c.image.labels.get("eai.release_seq", 0))
        prev = self._previous_release(service, cur)
        return {"rolled_back": service, "to": prev, "container": self._recreate_from(c, prev)}

    def clear_temp_path(self, service):
        c = self._container(service)
        argv = ["find", config.APPROVED_TEMP_PATH, "-maxdepth", "1", "-type", "f", "-name", "fill-*.bin", "-delete"]
        rc, out = c.exec_run(argv)
        if rc != 0:
            raise ExecutionError(f"clear_temp_path failed: {out.decode(errors='replace')[:200]}")
        return {"cleared": config.APPROVED_TEMP_PATH, "service": service}

    # ---------------------------------------------------------------- entry
    def run(self, runbook_id: str, service: str, actor: str, evidence_ids: list[str] | None = None):
        fn = {"restart_service": self.restart_service, "recreate_container": self.recreate_container,
              "rollback_release": self.rollback_release, "clear_temp_path": self.clear_temp_path}.get(runbook_id)
        if fn is None:
            raise ExecutionError(f"unknown runbook {runbook_id}")
        try:
            result = fn(service)
            self._log(runbook=runbook_id, service=service, actor=actor, ok=True, result=result,
                      evidence_ids=evidence_ids or [])
            return {"ok": True, **result}
        except Exception as e:  # audited, then re-raised as a clean error
            self._log(runbook=runbook_id, service=service, actor=actor, ok=False, error=str(e)[:300],
                      evidence_ids=evidence_ids or [])
            raise ExecutionError(str(e)) from e
