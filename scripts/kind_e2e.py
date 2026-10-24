"""Real, destructive-in-kind-only Package A acceptance check.

    python scripts/kind_e2e.py [--target shop|boutique]

--target shop (default): EternalAI's own 4-service shop (deploy/kind/shop/), the workload our trained models fit, with a
plain Prometheus. The brain runs in autopilot through Helm and must:
  1. frozen service (not Ready) -> EternalAI restart, by itself in autopilot (the kubelet does not repair a frozen
     process; see freeze_service);
  2. propose a rollback of a bad release and execute it only after approval;
  3. (nice-to-have) driver check, not a brain decision: KubernetesDriver scales a Deployment 1 -> 2 -> 1.
--target boutique: the earlier Online Boutique path (roadmap; prometheus-community chart), unchanged.

No fakes are used. All created resources live in the named throwaway kind cluster; Compose and unrelated clusters stay
intact. Port-forwards listen on 127.0.0.1 only.
"""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import secrets
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from eternalai.redact import redact  # noqa: E402
from eternalai.drivers.k8s import KubernetesDriver  # noqa: E402
from eternalai.sources.k8s_metrics import KubernetesProm, QUERIES  # noqa: E402
from eternalai.sources.service_map import discover_topology  # noqa: E402
from scripts.stack_lock import is_free, take, release  # noqa: E402; atomic shared lock
from scripts.k8s_window_deadline import bounded_timeout, remaining_work_seconds  # noqa: E402

IST = timezone(timedelta(hours=5, minutes=30))
TOOLS = Path(r"D:\eAI\tools")
KIND = TOOLS / "kind.exe"
HELM = TOOLS / "helm.exe"
KUBECTL = "kubectl"
CLUSTER = "eai"
NODE = f"{CLUSTER}-control-plane"           # the kind node container (single-node cluster)
MIN_FREE_GIB = 6.0
MANIFEST = "https://raw.githubusercontent.com/GoogleCloudPlatform/microservices-demo/v0.10.7/release/kubernetes-manifests.yaml"
MANIFEST_SHA256 = "ae3c20181c051048e6a5cae51fa530681affa4043ba60ae95d4f39e1262f2744"
PROM_CHART = "29.18.0"
PROM_ARCHIVE = ROOT / "runtime/prometheus-29.18.0.tgz"
PROM_SHA256 = "24f5f056dd5cb00e98ffb905c9c2779e810153f1b5a6306bf2cc2c5a4f02a0b9"
LATEST_MD = ROOT / "docs/results/kind_e2e.md"
LATEST_JSON = ROOT / "results/live-checks/kind_e2e.json"
CHECKS: list[dict] = []

# Our shop (deploy/kind/shop/)
SHOP_DIR = ROOT / "deploy/kind/shop"
SHOP_MANIFEST = SHOP_DIR / "shop.yaml"
SHOP_PROMETHEUS = SHOP_DIR / "prometheus.yaml"
SHOP_VALUES = SHOP_DIR / "values-shop.yaml"
SHOP_SERVICES = ("web", "orders", "payments", "inventory")
FROZEN_SERVICE = "inventory"                # frozen (not Ready); EternalAI must restart it in autopilot
BAD_SERVICE = "payments"                    # gets its v3-bad release; rollback must wait for approval
SCALE_SERVICE = "orders"                    # driver scale 1 -> 2 -> 1 (nice-to-have)
BRAIN_IMAGE = "eai/eternalai:k8s-dev"       # never :v2, which the Compose demo uses
PROMETHEUS_IMAGE = "prom/prometheus:v2.55.1"


def now_ist():
    return datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S IST")


def check(name: str, ok: bool, detail: str = ""):
    item = {"check": name, "result": "PASS" if ok else "FAIL", "detail": redact(str(detail)), "t": now_ist()}
    CHECKS.append(item)
    print(redact(f"[{item['result']}] {name}: {item['detail']}"), flush=True)
    return ok


def cmd(args, *, input_text=None, timeout=900, cleanup=False):
    process = subprocess.run([str(arg) for arg in args], cwd=ROOT, input=input_text,
                             capture_output=True, text=True, encoding="utf-8", errors="replace",
                             timeout=bounded_timeout(timeout, cleanup=cleanup))
    if process.returncode:
        raise RuntimeError(f"{Path(str(args[0])).name} {args[1]} exited {process.returncode}")
    return process.stdout.strip()


def free_memory_gb():
    class Status(ctypes.Structure):
        _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong),
                    ("total_phys", ctypes.c_ulonglong), ("avail_phys", ctypes.c_ulonglong),
                    ("total_page", ctypes.c_ulonglong), ("avail_page", ctypes.c_ulonglong),
                    ("total_virtual", ctypes.c_ulonglong), ("avail_virtual", ctypes.c_ulonglong),
                    ("avail_extended", ctypes.c_ulonglong)]
    status = Status()
    status.length = ctypes.sizeof(status)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        raise RuntimeError("could not read available memory")
    return status.avail_phys / (1024 ** 3)


def pod_status(namespace):
    """Record only pod readiness reasons, never logs, messages or Kubernetes credentials."""
    try:
        body = json.loads(cmd([KUBECTL, "-n", namespace, "get", "pods", "-o", "json"], timeout=30))
        return json.dumps([
            {"name": pod["metadata"]["name"], "phase": pod.get("status", {}).get("phase"),
             "conditions": [{"type": condition.get("type"), "reason": condition.get("reason")}
                            for condition in pod.get("status", {}).get("conditions", [])
                            if condition.get("status") == "False"],
             "waiting": [state["waiting"].get("reason")
                         for container in pod.get("status", {}).get("containerStatuses", [])
                         if (state := container.get("state", {})).get("waiting")],
             "ready": [container.get("ready", False)
                       for container in pod.get("status", {}).get("containerStatuses", [])]}
            for pod in body.get("items", [])], sort_keys=True)
    except (RuntimeError, ValueError, KeyError, subprocess.TimeoutExpired):
        return f"{namespace} pod status unavailable"


def monitoring_pod_status():
    return pod_status("monitoring")


def wait_until(predicate, seconds=240, step=3):
    remaining = remaining_work_seconds()
    if remaining is not None:
        seconds = min(seconds, max(0, remaining))
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            value = predicate()
            if value:
                return value
        except (httpx.HTTPError, ValueError, RuntimeError):
            pass
        time.sleep(step)
    return None


def port_forward(namespace, target, local, remote):
    bounded_timeout(1)
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    return subprocess.Popen([KUBECTL, "-n", namespace, "port-forward", "--address=127.0.0.1", target,
                             f"{local}:{remote}"], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            creationflags=flags)


def api_proxy():
    bounded_timeout(1)
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    return subprocess.Popen([KUBECTL, "proxy", "--address=127.0.0.1", "--port=18082"],
                            cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            creationflags=flags)


def deployment_ready(body, replicas=None):
    desired = body["spec"].get("replicas", 1)
    status = body.get("status", {})
    ready = (status.get("readyReplicas", 0) == desired
             and status.get("updatedReplicas", 0) == desired
             and status.get("replicas", 0) == desired
             and status.get("observedGeneration", 0) >= body["metadata"].get("generation", 0))
    return (replicas is None or desired == replicas) and ready


def wait_deployment(name, replicas=None, timeout=300, namespace="shop"):
    def ready():
        body = json.loads(cmd([KUBECTL, "-n", namespace, "get", "deployment", name, "-o", "json"]))
        return body if deployment_ready(body, replicas) else None
    return wait_until(ready, timeout, 5)


def pods(name, namespace="shop"):
    body = json.loads(cmd([KUBECTL, "-n", namespace, "get", "pods", "-l", f"app={name}", "-o", "json"]))
    return {item["metadata"]["name"] for item in body["items"]}


def api(method, path, token=None, **kwargs):
    headers = {"X-Approval-Token": token} if token else {}
    response = httpx.request(method, "http://127.0.0.1:18080" + path, headers=headers,
                             timeout=bounded_timeout(15), **kwargs)
    response.raise_for_status()
    return response.json()


def rbac_matrix(watch=True):
    principal = "system:serviceaccount:eternalai:eternalai"
    cases = [("get", "deployments.apps", "shop", True),
             ("patch", "deployments.apps", "shop", not watch),
             ("get", "pods", "shop", True), ("delete", "pods", "shop", not watch),
             ("get", "secrets", "shop", False), ("delete", "deployments.apps", "shop", False),
             ("create", "pods/exec", "shop", False), ("get", "deployments.apps", "kube-system", False),
             ("patch", "deployments.apps", "loadgen", False), ("get", "secrets", "eternalai", False)]
    results = {}
    for verb, resource, namespace, expected in cases:
        response = subprocess.run([KUBECTL, "auth", "can-i", verb, resource, "--as=" + principal,
                                   "-n", namespace], cwd=ROOT, capture_output=True, text=True, timeout=30)
        if response.stdout.strip().lower() not in ("yes", "no"):
            raise RuntimeError("kubectl auth can-i gave no yes/no answer")
        answer = response.stdout.strip().lower() == "yes"
        results[f"{namespace}:{verb}:{resource}"] = answer == expected
    return results


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ------------------------------------------------------------------ our shop: pure helpers (unit-tested)
def image_builds(compose_path: Path, bad_service: str = BAD_SERVICE) -> list[dict]:
    """docker build commands for the shop, read from docker-compose.yml so they cannot drift from Compose."""
    services = yaml.safe_load(compose_path.read_text(encoding="utf-8"))["services"]
    names = [*SHOP_SERVICES, f"{bad_service}-v3", "loadgen"]
    builds = []
    for name in names:
        svc = services[name]
        build = svc["build"] if isinstance(svc["build"], dict) else {"context": svc["build"]}
        builds.append({"tag": svc["image"], "context": build["context"],
                       "dockerfile": build.get("dockerfile"), "args": dict(build.get("args", {}))})
    brain = services["eternalai"]["build"]
    builds.append({"tag": BRAIN_IMAGE, "context": brain["context"], "dockerfile": brain["dockerfile"], "args": {}})
    return builds


def build_command(build: dict) -> list[str]:
    args = ["docker", "build", "-t", build["tag"]]
    if build.get("dockerfile"):
        args += ["-f", build["dockerfile"]]
    for key, value in sorted(build["args"].items()):
        args += ["--build-arg", f"{key}={value}"]
    return args + [build["context"]]


def running_container_id(pod: dict) -> str | None:
    """containerd ID of a Ready, running container of a pod (kubectl get pod -o json)."""
    if pod.get("metadata", {}).get("deletionTimestamp") or pod.get("status", {}).get("phase") != "Running":
        return None
    for status in pod.get("status", {}).get("containerStatuses", []):
        if status.get("ready") and "running" in status.get("state", {}) and status.get("containerID"):
            return status["containerID"].split("://", 1)[-1]
    return None


def process_pid(crictl_inspect: dict) -> int:
    pid = int(crictl_inspect["info"]["pid"])
    if pid <= 1:
        raise ValueError("refusing to signal pid <= 1 on the kind node")
    return pid


def automatic_actions(audit: list[dict], service: str, runbook: str, since: float) -> list[dict]:
    """Successful driver calls for (service, runbook) after `since` that the brain made (not this script)."""
    return [item for item in audit if item.get("service") == service and item.get("runbook") == runbook
            and item.get("ok") and item.get("actor") != "kind-e2e" and float(item.get("t", 0)) >= since]


ACTIVE_INCIDENT = ("open", "awaiting_approval", "executing", "verifying")      # as /status counts open_incidents


def active_incidents(incidents: list[dict]) -> list[dict]:
    return [i for i in incidents if i.get("status") in ACTIVE_INCIDENT]


def incident_with_action(incidents: list[dict], service: str, runbook: str, since: float) -> dict | None:
    """The first incident opened after `since` whose actions include `runbook` on `service` and that has a
    verification result."""
    for item in incidents:
        if float(item.get("opened_t", 0)) < since or not item.get("verification"):
            continue
        if any(a.get("service") == service and a.get("runbook_id") == runbook for a in item.get("actions", [])):
            return item
    return None


def actions_since(audit: list[dict], service: str, since: float) -> list[dict]:
    """Driver calls on `service` at or after `since` (verification records excluded)."""
    return [item for item in audit if item.get("service") == service and item.get("runbook") != "verification"
            and float(item.get("t", 0)) >= since]


TOKEN_FILE = ROOT / "runtime/kind_e2e_approval.token"    # git-ignored; deleted when the run ends
APPROVAL_WAIT_S = 840                                    # below the brain's 900 s approval TTL (values-shop.yaml)


def approval_instructions(incident_id: str, token_file: Path = TOKEN_FILE) -> str:
    """PowerShell for a human approval. The token is read from the git-ignored file and never printed."""
    return "\n".join([
        "",
        f"=== HUMAN APPROVAL NEEDED: rollback_release of {BAD_SERVICE} (incident {incident_id}) ===",
        "Check it first:  Invoke-RestMethod http://127.0.0.1:18080/approvals",
        "Approve it (replace YOUR-NAME), in a new PowerShell window:",
        f"  $t = (Get-Content '{token_file}' -Raw).Trim()",
        f"  Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:18080/approvals/{incident_id}/approve' "
        "-Headers @{'X-Approval-Token'=$t} -ContentType 'application/json' -Body '{\"approver\":\"YOUR-NAME\"}'",
        f"Waiting up to {APPROVAL_WAIT_S // 60} minutes. The script will not approve it.",
        ""])


def human_approval(incident: dict, audit: list[dict], service: str, runbook: str) -> dict | None:
    """Approver and wait for the approved action of an incident: wait = execution (audit, actor human:<name>) minus
    the time the brain proposed it. None until the approved action has executed."""
    action = next((a for a in incident.get("actions", []) if a.get("service") == service
                   and a.get("runbook_id") == runbook and a.get("approved_by")), None)
    if action is None:
        return None
    approver = action["approved_by"]
    executed = next((item for item in audit if item.get("service") == service and item.get("runbook") == runbook
                     and item.get("actor") == f"human:{approver}" and float(item.get("t", 0)) >= float(action["t"])),
                    None)
    if executed is None:
        return None
    return {"approver": approver, "wait_s": float(executed["t"]) - float(action["t"]), "proposed_t": action["t"],
            "executed_t": executed["t"], "ok": bool(executed.get("ok"))}


def deployment_image(body: dict, container: str) -> str | None:
    for item in body["spec"]["template"]["spec"]["containers"]:
        if item["name"] == container:
            return item["image"]
    return None


def freeze_service(service: str) -> str:
    """Stop (SIGSTOP) the service's process from the kind node. The pod stays Running, so the kubelet does not restart
    it (no livenessProbe, as Compose has restart: "no"); its readinessProbe fails and /metrics stops answering. This is
    a frozen service (not Ready) that only EternalAI's restart repairs. Returns the frozen pod's name."""
    body = json.loads(cmd([KUBECTL, "-n", "shop", "get", "pods", "-l", f"app={service}", "-o", "json"]))
    for pod in body["items"]:
        cid = running_container_id(pod)
        if cid:
            pid = process_pid(json.loads(cmd(["docker", "exec", NODE, "crictl", "inspect", cid])))
            cmd(["docker", "exec", NODE, "kill", "-STOP", str(pid)])
            return pod["metadata"]["name"]
    raise RuntimeError(f"no Ready {service} pod to freeze")


# ------------------------------------------------------------------ results
def write_results(head, run_id, started_at, image_id, target="boutique", configuration=None, branch=None):
    finished_at = now_ist()
    shop = target == "shop"
    if configuration is None:
        configuration = {
            "kind_config_sha256": file_hash(ROOT / "deploy/kind/kind-cluster.yaml"),
            "helm_values_sha256": file_hash(ROOT / "deploy/helm/eternalai/values.yaml"),
            "rulebook_source": "deploy/helm/eternalai/values.yaml#rulebook",
            "online_boutique_manifest_sha256": MANIFEST_SHA256,
            "prometheus_chart_version": PROM_CHART,
            "prometheus_chart_archive_sha256": PROM_SHA256,
            "namespace": "shop", "mode_initial": "watch", "mode_final": "ask",
            "ports": [18080, 18081, 18082]}
    result = {"execution_id": run_id, "target": target, "started_at_ist": started_at, "finished_at_ist": finished_at,
              "branch": branch or "unknown", "commit": head,
              "image": {"tag": BRAIN_IMAGE, "id": image_id, "built_from": head if image_id else None},
              "configuration": configuration, "checks": CHECKS}
    stem = f"kind_e2e_shop_{run_id}" if shop else f"kind_e2e_{run_id}"
    out_md = ROOT / f"docs/results/{stem}.md"
    out_json = ROOT / f"results/live-checks/{stem}.json"
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(result, indent=2)
    with out_json.open("x", encoding="utf-8") as stream:
        stream.write(content + "\n")
    title = ("# Kubernetes kind end-to-end check: our 4-service shop" if shop
             else "# Kubernetes kind end-to-end check")
    passed = bool(CHECKS) and all(c["result"] == "PASS" for c in CHECKS)
    rows = [title, "",
            f"**{'verified live' if passed else 'live run with failures'}** on a local kind cluster "
            f"(`{'scripts/kind_e2e.py --target shop' if shop else 'scripts/kind_e2e.py --target boutique'}`); "
            "every row below was written by the script.", "",
            f"- Execution: `{run_id}`",
            f"- Time: {started_at} to {finished_at}", f"- Commit: `{head}`",
            f"- Image: `{BRAIN_IMAGE}` (`{image_id or 'not built'}`)",
            f"- Configuration: [JSON result](../../results/live-checks/{out_json.name})", "",
            "| Check | Result | Detail |", "|---|---|---|"]
    rows += [f"| {c['check']} | {c['result']} | {c['detail'].replace('|', '/')} |" for c in CHECKS]
    markdown = "\n".join(rows) + "\n"
    with out_md.open("x", encoding="utf-8") as stream:
        stream.write(markdown)
    if not shop:   # the shop run writes only its execution-specific files; the integrator links them
        LATEST_JSON.write_text(content + "\n", encoding="utf-8")
        LATEST_MD.write_text(markdown, encoding="utf-8")
    return out_md, out_json


def shop_configuration():
    return {"target": "shop",
            "kind_config_sha256": file_hash(ROOT / "deploy/kind/kind-cluster.yaml"),
            "shop_manifest_sha256": file_hash(SHOP_MANIFEST),
            "prometheus_manifest_sha256": file_hash(SHOP_PROMETHEUS),
            "helm_values_sha256": file_hash(ROOT / "deploy/helm/eternalai/values.yaml"),
            "shop_values_sha256": file_hash(SHOP_VALUES),
            "rulebook_source": "deploy/helm/eternalai/values.yaml#rulebook",
            "prometheus_image": PROMETHEUS_IMAGE,
            "frozen_service": FROZEN_SERVICE, "bad_release_service": BAD_SERVICE, "scale_service": SCALE_SERVICE,
            "namespaces": ["shop", "loadgen", "monitoring", "eternalai"],
            "mode_initial": "watch", "mode_final": "autopilot", "ports": [18080, 18081, 18082],
            "approval_wait_limit_s": APPROVAL_WAIT_S}


# ------------------------------------------------------------------ shared start and teardown
def preflight(image_origin):
    if not KIND.is_file() or not HELM.is_file():
        raise RuntimeError("verified kind.exe and helm.exe are required in D:\\eAI\\tools")
    if not is_free():
        raise RuntimeError("the shared Docker lock is occupied")
    available = free_memory_gb()
    if available < MIN_FREE_GIB:
        raise RuntimeError(f"only {available:.2f} GiB available; kind requires about {MIN_FREE_GIB:g} GiB")
    try:
        take("rajat", "kind e2e", image_origin)
    except SystemExit:
        raise RuntimeError("could not acquire shared Docker lock") from None
    return available


def preflight_state(available):
    if cmd(["docker", "ps", "--filter", "label=com.docker.compose.project=eai", "--format", "{{.ID}}"]):
        raise RuntimeError("the Compose stack is running")
    if cmd([KIND, "get", "clusters"]).splitlines():
        raise RuntimeError("a kind cluster is already running")
    check("preflight", True, f"Compose stopped, no kind cluster, {available:.2f} GiB free")


def create_secret(namespace, name, value):
    manifest = {"apiVersion": "v1", "kind": "Secret", "metadata": {"name": name, "namespace": namespace},
                "stringData": {"token": value}}
    cmd([KUBECTL, "apply", "-f", "-"], input_text=json.dumps(manifest))


# ------------------------------------------------------------------ our shop
def run_shop(head, state, approval="manual"):
    available = preflight(state["origin"])
    state["held"] = True
    preflight_state(available)

    builds = image_builds(ROOT / "docker-compose.yml")
    for build in builds:
        cmd(build_command(build), timeout=1800)
    cmd(["docker", "pull", PROMETHEUS_IMAGE], timeout=900)
    state["image_id"] = cmd(["docker", "image", "inspect", "--format", "{{.Id}}", BRAIN_IMAGE])
    check("images", True, f"{len(builds)} images built from {head[:7]} ({', '.join(b['tag'] for b in builds)}); "
                          f"{PROMETHEUS_IMAGE} pulled")

    state["cluster"] = True
    cmd([KIND, "create", "cluster", "--config", "deploy/kind/kind-cluster.yaml", "--name", CLUSTER], timeout=1200)
    check("cluster", True, "pinned single-node kind cluster created")
    for tag in [b["tag"] for b in builds] + [PROMETHEUS_IMAGE]:
        cmd([KIND, "load", "docker-image", tag, "--name", CLUSTER], timeout=900)
    check("images_loaded", True, "all images loaded into the kind node")

    cmd([KUBECTL, "apply", "-f", str(SHOP_MANIFEST)])
    create_secret("shop", "shop-chaos", secrets.token_urlsafe(32))      # random, never written to disk
    cmd([KUBECTL, "apply", "-f", str(SHOP_PROMETHEUS)])
    unready = [name for name in SHOP_SERVICES if wait_deployment(name, timeout=300) is None]
    if wait_deployment("loadgen", timeout=180, namespace="loadgen") is None:
        unready.append("loadgen")
    check("shop_ready", not unready, f"unready: {','.join(unready) or 'none'}" + (
        f"; {pod_status('shop')}" if unready else ""))
    if unready:
        raise RuntimeError("the shop did not become Ready")
    if wait_deployment("prometheus", timeout=300, namespace="monitoring") is None:
        check("prometheus", False, monitoring_pod_status())
        raise RuntimeError("Prometheus did not become Ready")
    check("prometheus", True, f"plain {PROMETHEUS_IMAGE} Ready")

    state["forwards"].append(port_forward("monitoring", "service/prometheus", 18081, 9090))
    def scraped():
        body = httpx.get("http://127.0.0.1:18081/api/v1/query", params={"query": 'up{job="app"}'}, timeout=5).json()
        values = {r["metric"].get("instance_name"): r["value"][1] for r in body["data"]["result"]}
        return values if all(values.get(s) == "1" for s in SHOP_SERVICES) else None
    up = wait_until(scraped, 120, 3)
    check("metrics_scraped", bool(up), f"up{{job=app}} per instance_name: {json.dumps(up, sort_keys=True)}")

    cmd([KUBECTL, "create", "namespace", "eternalai"])
    token = secrets.token_urlsafe(32)
    create_secret("eternalai", "eai-e2e-approval", token)
    if approval == "manual":                  # for the human approver only; git-ignored, deleted at the end
        TOKEN_FILE.parent.mkdir(exist_ok=True)
        TOKEN_FILE.write_text(token, encoding="utf-8")
        state["token_file"] = TOKEN_FILE
    cmd([HELM, "install", "eternalai", "deploy/helm/eternalai", "-n", "eternalai", "-f", str(SHOP_VALUES),
         "--set", "approvalToken.existingSecret=eai-e2e-approval"], timeout=300)
    cmd([KUBECTL, "-n", "eternalai", "rollout", "status", "deployment/eternalai", "--timeout=300s"])
    state["forwards"].append(port_forward("eternalai", "service/eternalai", 18080, 8000))
    status = wait_until(lambda: api("GET", "/status"), 90)
    check("brain_ready", bool(status), "Helm release Ready; /status answered through 127.0.0.1:18080")
    if not status:
        raise RuntimeError("brain did not become reachable")
    models = status.get("models", {})
    check("trained_models", all(models.get(k) for k in ("detectors", "classifier", "ranker")),
          f"models loaded: {json.dumps(models, sort_keys=True)}; fallbacks: {status.get('fallbacks_in_use')}")

    matrix = rbac_matrix()
    check("rbac_watch", all(matrix.values()), json.dumps(matrix, sort_keys=True))
    if not all(matrix.values()):
        raise RuntimeError("watch RBAC matrix failed")
    topology = api("GET", "/services")["topology"]
    expected = {"web": ["orders", "inventory"], "orders": ["inventory", "payments"], "inventory": [], "payments": []}
    check("topology", topology == expected and not status.get("topology_fallback"),
          f"annotation graph exposed by brain: {json.dumps(topology, sort_keys=True)}")

    cmd([HELM, "upgrade", "eternalai", "deploy/helm/eternalai", "-n", "eternalai", "-f", str(SHOP_VALUES),
         "--set", "mode=autopilot", "--set", "approvalToken.existingSecret=eai-e2e-approval"], timeout=300)
    cmd([KUBECTL, "-n", "eternalai", "rollout", "status", "deployment/eternalai", "--timeout=300s"])
    write_matrix = rbac_matrix(watch=False)
    check("rbac_autopilot", all(write_matrix.values()), json.dumps(write_matrix, sort_keys=True))
    if not all(write_matrix.values()):
        raise RuntimeError("autopilot RBAC matrix failed")
    state["forwards"][-1].terminate()
    state["forwards"][-1].wait(timeout=5)
    state["forwards"][-1] = port_forward("eternalai", "service/eternalai", 18080, 8000)
    wait_until(lambda: api("GET", "/status"), 90)
    api("POST", "/mode", token, json={"mode": "autopilot"})
    mode = api("GET", "/status").get("mode")
    check("mode", mode == "autopilot", f"brain mode {mode}")

    # Let the brain see a normal shop first (feature window + persistence), then require no open incident.
    time.sleep(60)
    open_before = active_incidents(api("GET", "/incidents"))
    check("baseline_quiet", not open_before, f"{len(open_before)} active incidents after 60 s of normal load")

    # 1. frozen service (not Ready) -> EternalAI restart (MUST)
    t0 = time.time()
    frozen = freeze_service(FROZEN_SERVICE)
    check("frozen_service", True, f"{FROZEN_SERVICE} process stopped in pod {frozen} (pod stays Running, not Ready)")
    restarted = wait_until(lambda: automatic_actions(api("GET", "/audit"), FROZEN_SERVICE, "restart_service", t0), 240, 3)
    check("auto_restart", bool(restarted),
          f"brain restart_service on {FROZEN_SERVICE} without approval: {len(restarted or [])} audited call(s)")
    replaced = wait_until(lambda: wait_deployment(FROZEN_SERVICE, timeout=5)
                          if frozen not in pods(FROZEN_SERVICE) else None, 240, 5)
    frozen_incident = wait_until(lambda: incident_with_action(api("GET", "/incidents"), FROZEN_SERVICE,
                                                             "restart_service", t0 - 5), 300, 5)
    outcome = (frozen_incident or {}).get("verification", {}).get("outcome")
    check("frozen_service_recovered", bool(replaced and outcome == "recovered"),
          f"frozen pod replaced: {bool(replaced)}; incident verification: {outcome}")

    # 2. bad deploy -> rollback only after approval (MUST)
    time.sleep(30)                                   # let the restarted service settle before the next fault
    good = deployment_image(json.loads(cmd([KUBECTL, "-n", "shop", "get", "deployment", BAD_SERVICE, "-o", "json"])),
                            BAD_SERVICE)
    bad = f"eai/{BAD_SERVICE}:v3-bad"
    t1 = time.time()
    cmd([KUBECTL, "-n", "shop", "set", "image", f"deployment/{BAD_SERVICE}", f"{BAD_SERVICE}={bad}"])
    check("bad_release", True, f"{BAD_SERVICE}: {good} -> {bad}")
    pending = wait_until(lambda: next((item for item in api("GET", "/approvals")
                                       if item.get("service") == BAD_SERVICE
                                       and item.get("runbook_id") == "rollback_release"), None), 300, 3)
    check("rollback_waits", bool(pending), "brain proposed rollback_release and waits for approval")
    if not pending:
        raise RuntimeError("brain did not propose an approved rollback")
    current = json.loads(cmd([KUBECTL, "-n", "shop", "get", "deployment", BAD_SERVICE, "-o", "json"]))
    acted = actions_since(api("GET", "/audit"), BAD_SERVICE, t1)
    no_action = deployment_image(current, BAD_SERVICE) == bad and not acted
    check("no_preapproval_action", no_action, f"image still {deployment_image(current, BAD_SERVICE)}; "
                                              f"{len(acted)} {BAD_SERVICE} action(s) before approval")
    if not no_action:
        raise RuntimeError(f"{BAD_SERVICE} changed before approval")
    iid = pending["incident_id"]
    if approval == "auto":
        api("POST", f"/approvals/{iid}/approve", token, json={"approver": "kind-e2e-auto"})
    else:
        print(approval_instructions(iid), flush=True)
    human = wait_until(lambda: human_approval(next(i for i in api("GET", "/incidents") if i["id"] == iid),
                                              api("GET", "/audit"), BAD_SERVICE, "rollback_release"),
                       APPROVAL_WAIT_S if approval == "manual" else 120, 2)
    by_human = bool(human) and (approval == "auto" or not human["approver"].startswith("kind-e2e"))
    check("approval", by_human,
          (f"approved by {human['approver']} ({'script, auto' if approval == 'auto' else 'human, manual'}); "
           f"waited {human['wait_s']:.0f} s from proposal to approved execution" if human
           else f"no approval within {APPROVAL_WAIT_S if approval == 'manual' else 120} s"))
    if not human:
        raise RuntimeError("the rollback was not approved")
    rolled = wait_until(lambda: (lambda body: body if deployment_image(body, BAD_SERVICE) == good
                                 and deployment_ready(body) else None)(
        json.loads(cmd([KUBECTL, "-n", "shop", "get", "deployment", BAD_SERVICE, "-o", "json"]))), 300, 5)
    incident = wait_until(lambda: next((item for item in api("GET", "/incidents")
                                        if item["id"] == pending["incident_id"] and item.get("verification")), None), 300)
    rb_outcome = (incident or {}).get("verification", {}).get("outcome")
    check("approved_rollback", bool(rolled and rb_outcome == "recovered"),
          f"image back to {good} and Ready: {bool(rolled)}; incident verification: {rb_outcome}; "
          f"{len(automatic_actions(api('GET', '/audit'), BAD_SERVICE, 'rollback_release', t1))} audited rollback(s)")

    # 3. scale (nice-to-have): the driver, not the brain (no scale-out runbook in the rulebook)
    state["forwards"].append(api_proxy())
    wait_until(lambda: httpx.get("http://127.0.0.1:18082/version", timeout=5).status_code == 200, 30)
    from kubernetes import client as kube_client
    api_config = kube_client.Configuration()
    api_config.host = "http://127.0.0.1:18082"
    kube_api = kube_client.ApiClient(configuration=api_config)
    driver = KubernetesDriver("shop", ["shop"], apps=kube_client.AppsV1Api(kube_api),
                              core=kube_client.CoreV1Api(kube_api), audit_path=ROOT / "runtime/kind_e2e_driver.jsonl")
    driver.scale_to(SCALE_SERVICE, 2)
    up2 = wait_deployment(SCALE_SERVICE, 2, 240)
    driver.scale_to(SCALE_SERVICE, 1)
    down1 = wait_deployment(SCALE_SERVICE, 1, 240)
    check("driver_scale", bool(up2 and down1) and all(item["ok"] for item in driver.audit),
          f"driver check, not a brain decision (nice-to-have): {SCALE_SERVICE} 1 -> 2 -> 1 through "
          "KubernetesDriver.scale_to")


# ------------------------------------------------------------------ Online Boutique (roadmap; unchanged path)
def run_boutique(head, state):
    available = preflight(state["origin"])
    state["held"] = True
    preflight_state(available)

    state["cluster"] = True
    cmd([KIND, "create", "cluster", "--config", "deploy/kind/kind-cluster.yaml", "--name", CLUSTER], timeout=1200)
    check("cluster", True, "pinned single-node kind cluster created")
    cmd([KUBECTL, "create", "namespace", "monitoring"])
    PROM_ARCHIVE.parent.mkdir(exist_ok=True)
    if not PROM_ARCHIVE.is_file():
        cmd([HELM, "pull", "oci://ghcr.io/prometheus-community/charts/prometheus",
             "--version", PROM_CHART, "--destination", str(PROM_ARCHIVE.parent)], timeout=300)
    if file_hash(PROM_ARCHIVE) != PROM_SHA256:
        raise RuntimeError("pinned Prometheus chart checksum mismatch")
    cmd([HELM, "install", "prometheus", str(PROM_ARCHIVE), "-n", "monitoring",
         "--set", "alertmanager.enabled=false", "--set", "prometheus-pushgateway.enabled=false",
         "--set", "server.persistentVolume.enabled=false"], timeout=1200)
    check("prometheus_install", True, f"chart {PROM_CHART} installed")
    try:
        cmd([KUBECTL, "-n", "monitoring", "rollout", "status", "deployment/prometheus-server", "--timeout=300s"])
    except (RuntimeError, subprocess.TimeoutExpired):
        check("prometheus_rollout", False, monitoring_pod_status())
        raise
    check("prometheus", True, f"chart {PROM_CHART} Ready")

    cmd([KUBECTL, "create", "namespace", "shop"])
    manifest = urllib.request.urlopen(MANIFEST, timeout=bounded_timeout(60)).read()
    digest = hashlib.sha256(manifest).hexdigest()
    if digest.lower() != MANIFEST_SHA256:
        raise RuntimeError("pinned Online Boutique manifest checksum mismatch")
    path = ROOT / "runtime/online-boutique-v0.10.7.yaml"
    path.parent.mkdir(exist_ok=True)
    path.write_bytes(manifest)
    cmd([KUBECTL, "-n", "shop", "apply", "-f", str(path)])
    cmd(["powershell", "-NoProfile", "-File", "deploy/online-boutique/annotate.ps1", "shop"])
    deployments = json.loads(cmd([KUBECTL, "-n", "shop", "get", "deployments", "-o", "json"]))["items"]
    missing = [item["metadata"]["name"] for item in deployments
               if wait_deployment(item["metadata"]["name"], timeout=420) is None]
    check("boutique_ready", not missing, f"unready Deployments: {','.join(missing)}")
    if missing:
        raise RuntimeError("Online Boutique did not become Ready")

    cmd(["docker", "build", "-t", BRAIN_IMAGE, "-f", "eternalai/Dockerfile", "."], timeout=1800)
    state["image_id"] = cmd(["docker", "image", "inspect", "--format", "{{.Id}}", BRAIN_IMAGE])
    cmd([KIND, "load", "docker-image", BRAIN_IMAGE, "--name", CLUSTER], timeout=900)
    check("brain_image", True, f"{BRAIN_IMAGE} {state['image_id']} built from {head[:7]}")
    cmd([KUBECTL, "create", "namespace", "eternalai"])
    token = secrets.token_urlsafe(32)
    create_secret("eternalai", "eai-e2e-approval", token)
    cmd([HELM, "install", "eternalai", "deploy/helm/eternalai", "-n", "eternalai",
         "--set", "approvalToken.existingSecret=eai-e2e-approval"], timeout=300)
    cmd([KUBECTL, "-n", "eternalai", "rollout", "status", "deployment/eternalai", "--timeout=300s"])
    forwards = state["forwards"]
    forwards.append(port_forward("eternalai", "service/eternalai", 18080, 8000))
    status = wait_until(lambda: api("GET", "/status"), 90)
    check("brain_ready", bool(status), "/status answered through 18080")
    if not status:
        raise RuntimeError("brain did not become reachable")

    matrix = rbac_matrix()
    check("rbac", all(matrix.values()), json.dumps(matrix, sort_keys=True))
    if not all(matrix.values()):
        raise RuntimeError("watch RBAC matrix failed")
    forwards.append(api_proxy())
    wait_until(lambda: httpx.get("http://127.0.0.1:18082/version", timeout=5).status_code == 200, 30)
    from kubernetes import client as kube_client
    api_config = kube_client.Configuration()
    api_config.host = "http://127.0.0.1:18082"
    kube_api = kube_client.ApiClient(configuration=api_config)
    apps, core = kube_client.AppsV1Api(kube_api), kube_client.CoreV1Api(kube_api)
    graph, fallback = discover_topology(apps, ["shop"])
    exposed = api("GET", "/services")["topology"]
    check("topology", not fallback and exposed == graph and
          graph.get("cartservice") == ["redis-cart"], "annotation graph exposed by brain")

    forwards.append(port_forward("monitoring", "service/prometheus-server", 18081, 80))
    wait_until(lambda: httpx.get("http://127.0.0.1:18081/-/ready", timeout=5).status_code == 200, 60)
    prom = KubernetesProm("http://127.0.0.1:18081", "shop")
    observed = {}
    for name in graph:
        frame = prom.signals(name, 60)
        observed[name] = [key for key in QUERIES if frame[key].notna().any()]
    required_metrics = {"cpu_cores", "mem_bytes", "up", "restarts_3m"}
    check("metrics", all(required_metrics <= set(keys) for keys in observed.values()), json.dumps(observed))

    driver = KubernetesDriver("shop", ["shop"], apps=apps, core=core)
    before = pods("currencyservice")
    driver.run("restart_service", "currencyservice", "kind-e2e")
    after_ready = wait_until(lambda: wait_deployment("currencyservice", timeout=5)
                             if pods("currencyservice") != before else None, 240, 5)
    check("restart", bool(after_ready), "currencyservice pods replaced")
    driver.scale_to("recommendationservice", 2)
    up = wait_deployment("recommendationservice", 2, 240)
    driver.scale_to("recommendationservice", 1)
    down = wait_deployment("recommendationservice", 1, 240)
    check("scale", bool(up and down), "recommendationservice 1 -> 2 -> 1")
    before = pods("adservice")
    driver.run("recreate_container", "adservice", "kind-e2e")
    replaced = wait_until(lambda: wait_deployment("adservice", timeout=5)
                          if pods("adservice") != before else None, 240, 5)
    check("pod_replacement", bool(replaced), "adservice pod replaced")
    check("driver_audit", all(item["ok"] for item in driver.audit), f"{len(driver.audit)} audited driver calls")

    cmd([HELM, "upgrade", "eternalai", "deploy/helm/eternalai", "-n", "eternalai",
         "--set", "mode=ask", "--set", "approvalToken.existingSecret=eai-e2e-approval"])
    cmd([KUBECTL, "-n", "eternalai", "rollout", "status", "deployment/eternalai", "--timeout=300s"])
    ask_matrix = rbac_matrix(watch=False)
    check("rbac_ask", all(ask_matrix.values()), json.dumps(ask_matrix, sort_keys=True))
    if not all(ask_matrix.values()):
        raise RuntimeError("ask RBAC matrix failed")
    forwards[0].terminate()
    forwards[0].wait(timeout=5)
    forwards[0] = port_forward("eternalai", "service/eternalai", 18080, 8000)
    wait_until(lambda: api("GET", "/status"), 60)
    api("POST", "/mode", token, json={"mode": "ask"})
    current = apps.read_namespaced_deployment("productcatalogservice", "shop")
    audit_before = len(api("GET", "/audit"))
    image = current.spec.template.spec.containers[0].image
    bad = image.rsplit(":", 1)[0] + ":does-not-exist"
    cmd([KUBECTL, "-n", "shop", "set", "image", "deployment/productcatalogservice", "server=" + bad])
    pending = wait_until(lambda: next((item for item in api("GET", "/approvals")
                                        if item.get("service") == "productcatalogservice"
                                        and item.get("runbook_id") == "rollback_release"), None), 240)
    check("rollback_waits", bool(pending), "bad-image rollback requires approval")
    if not pending:
        raise RuntimeError("brain did not propose an approved rollback")
    unchanged = apps.read_namespaced_deployment("productcatalogservice", "shop")
    no_action = unchanged.spec.template.spec.containers[0].image == bad and not any(
        item.get("service") == "productcatalogservice" and item.get("runbook") != "verification"
        for item in api("GET", "/audit")[audit_before:])
    check("no_preapproval_action", no_action, "no productcatalogservice action before approval")
    if not no_action:
        raise RuntimeError("productcatalogservice changed before approval")
    api("POST", f"/approvals/{pending['incident_id']}/approve", token, json={"approver": "kind-e2e"})
    recovered = wait_deployment("productcatalogservice", timeout=300)
    incident = wait_until(lambda: next((item for item in api("GET", "/incidents")
                                        if item["id"] == pending["incident_id"] and item.get("verification")), None), 300)
    check("approved_rollback", bool(recovered and incident and incident["verification"]["outcome"] == "recovered"),
          "Deployment Ready and incident verification recorded")


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description="Package A kind end-to-end check")
    ap.add_argument("--target", choices=("shop", "boutique"), default="shop",
                    help="shop: our 4-service shop (default); boutique: Online Boutique (roadmap)")
    ap.add_argument("--approval", choices=("manual", "auto"), default="manual",
                    help="shop rollback approval: manual (default; a human approves with the token file) or auto "
                         "(the script approves; not a verified human-approval run)")
    return ap.parse_args(argv)


def main(argv=()):
    args = parse_args(list(argv))
    head = cmd(["git", "rev-parse", "HEAD"])
    branch = cmd(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    run_id = datetime.now(IST).strftime("%Y%m%dT%H%M%S") + "-" + secrets.token_hex(4)
    started_at = now_ist()
    state = {"origin": f"{branch}@{head[:7]}", "held": False, "cluster": False, "forwards": [], "image_id": None,
             "token_file": None}
    try:
        if args.target == "shop":
            run_shop(head, state, args.approval)
        else:
            run_boutique(head, state)
    except Exception as exc:
        check("aborted", False, f"{type(exc).__name__}: {exc}")
    finally:
        if state["token_file"]:
            Path(state["token_file"]).unlink(missing_ok=True)
        if args.target == "shop" and state["cluster"]:
            check("shop_state_at_end", True, pod_status("shop"))
        for forward in state["forwards"]:
            forward.terminate()
            try:
                forward.wait(timeout=5)
            except subprocess.TimeoutExpired:
                forward.kill()
        if state["cluster"]:
            try:
                cmd([HELM, "uninstall", "eternalai", "-n", "eternalai"], timeout=120, cleanup=True)
            except Exception:
                pass
            try:
                cmd([KIND, "delete", "cluster", "--name", CLUSTER], timeout=600, cleanup=True)
                check("teardown", True, "only the eai kind cluster removed")
            except Exception as exc:
                check("teardown", False, type(exc).__name__)
        if state["held"]:
            try:
                release("rajat", state["origin"])
                check("lock_release", True, "atomic owner file released")
            except (Exception, SystemExit) as exc:
                check("lock_release", False, type(exc).__name__)
        configuration = ({**shop_configuration(), "approval": args.approval} if args.target == "shop" else None)
        write_results(head, run_id, started_at, state["image_id"], args.target, configuration, branch)
    return 0 if CHECKS and all(item["result"] == "PASS" for item in CHECKS) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
