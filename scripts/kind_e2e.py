"""Real, destructive-in-kind-only Package A acceptance check.

Run only in Codex's assigned Docker slot. No fakes are used. All created resources
live in the named throwaway kind cluster; Compose and unrelated clusters stay intact.
"""
from __future__ import annotations

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

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from eternalai.redact import redact  # noqa: E402
from eternalai.drivers.k8s import KubernetesDriver  # noqa: E402
from eternalai.sources.k8s_metrics import KubernetesProm, QUERIES  # noqa: E402
from eternalai.sources.service_map import discover_topology  # noqa: E402
from scripts.stack_lock import is_free, take, release  # noqa: E402; atomic shared lock

IST = timezone(timedelta(hours=5, minutes=30))
TOOLS = Path(r"D:\eAI\tools")
KIND = TOOLS / "kind.exe"
HELM = TOOLS / "helm.exe"
KUBECTL = "kubectl"
MANIFEST = "https://raw.githubusercontent.com/GoogleCloudPlatform/microservices-demo/v0.10.7/release/kubernetes-manifests.yaml"
MANIFEST_SHA256 = "ae3c20181c051048e6a5cae51fa530681affa4043ba60ae95d4f39e1262f2744"
PROM_CHART = "29.18.0"
PROM_ARCHIVE = ROOT / "runtime/prometheus-29.18.0.tgz"
PROM_SHA256 = "24f5f056dd5cb00e98ffb905c9c2779e810153f1b5a6306bf2cc2c5a4f02a0b9"
LATEST_MD = ROOT / "docs/results/kind_e2e.md"
LATEST_JSON = ROOT / "results/live-checks/kind_e2e.json"
CHECKS: list[dict] = []


def now_ist():
    return datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S IST")


def check(name: str, ok: bool, detail: str = ""):
    item = {"check": name, "result": "PASS" if ok else "FAIL", "detail": redact(str(detail)), "t": now_ist()}
    CHECKS.append(item)
    print(redact(f"[{item['result']}] {name}: {item['detail']}"), flush=True)
    return ok


def cmd(args, *, input_text=None, timeout=900):
    process = subprocess.run([str(arg) for arg in args], cwd=ROOT, input=input_text,
                             capture_output=True, text=True, timeout=timeout)
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


def wait_until(predicate, seconds=240, step=3):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            value = predicate()
            if value:
                return value
        except (httpx.HTTPError, ValueError):
            pass
        time.sleep(step)
    return None


def port_forward(namespace, target, local, remote):
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    return subprocess.Popen([KUBECTL, "-n", namespace, "port-forward", target, f"{local}:{remote}"],
                            cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            creationflags=flags)


def api_proxy():
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    return subprocess.Popen([KUBECTL, "proxy", "--address=127.0.0.1", "--port=18082"],
                            cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            creationflags=flags)


def wait_deployment(name, replicas=None, timeout=300):
    def ready():
        body = json.loads(cmd([KUBECTL, "-n", "shop", "get", "deployment", name, "-o", "json"]))
        desired = body["spec"].get("replicas", 1)
        status = body.get("status", {})
        ready = (status.get("readyReplicas", 0) == desired
                 and status.get("updatedReplicas", 0) == desired
                 and status.get("observedGeneration", 0) >= body["metadata"].get("generation", 0))
        return body if (replicas is None or desired == replicas) and ready else None
    return wait_until(ready, timeout, 5)


def pods(name):
    body = json.loads(cmd([KUBECTL, "-n", "shop", "get", "pods", "-l", f"app={name}", "-o", "json"]))
    return {item["metadata"]["name"] for item in body["items"]}


def api(method, path, token=None, **kwargs):
    headers = {"X-Approval-Token": token} if token else {}
    response = httpx.request(method, "http://127.0.0.1:18080" + path, headers=headers, timeout=15, **kwargs)
    response.raise_for_status()
    return response.json()


def rbac_matrix(watch=True):
    principal = "system:serviceaccount:eternalai:eternalai"
    cases = [("get", "deployments.apps", "shop", True),
             ("patch", "deployments.apps", "shop", not watch),
             ("get", "pods", "shop", True), ("delete", "pods", "shop", not watch),
             ("get", "secrets", "shop", False), ("delete", "deployments.apps", "shop", False),
             ("create", "pods/exec", "shop", False), ("get", "deployments.apps", "kube-system", False)]
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


def write_results(head, run_id, started_at, image_id):
    finished_at = now_ist()
    result = {"execution_id": run_id, "started_at_ist": started_at, "finished_at_ist": finished_at,
              "branch": "friend/phase2-k8s", "commit": head,
              "image": {"tag": "eai/eternalai:k8s-dev", "id": image_id,
                        "built_from": head if image_id else None},
              "configuration": {
                  "kind_config_sha256": file_hash(ROOT / "deploy/kind/kind-cluster.yaml"),
                  "helm_values_sha256": file_hash(ROOT / "deploy/helm/eternalai/values.yaml"),
                  "rulebook_source": "deploy/helm/eternalai/values.yaml#rulebook",
                  "online_boutique_manifest_sha256": MANIFEST_SHA256,
                  "prometheus_chart_version": PROM_CHART,
                  "prometheus_chart_archive_sha256": PROM_SHA256,
                  "namespace": "shop", "mode_initial": "watch", "mode_final": "ask",
                  "ports": [18080, 18081, 18082]},
              "checks": CHECKS}
    out_md = ROOT / f"docs/results/kind_e2e_{run_id}.md"
    out_json = ROOT / f"results/live-checks/kind_e2e_{run_id}.json"
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(result, indent=2)
    with out_json.open("x", encoding="utf-8") as stream:
        stream.write(content + "\n")
    rows = ["# Kubernetes kind end-to-end check", "", f"- Execution: `{run_id}`",
            f"- Time: {started_at} to {finished_at}", f"- Commit: `{head}`",
            f"- Image: `eai/eternalai:k8s-dev` (`{image_id or 'not built'}`)",
            f"- Configuration: [JSON result](../../results/live-checks/{out_json.name})", "",
            "| Check | Result | Detail |", "|---|---|---|"]
    rows += [f"| {c['check']} | {c['result']} | {c['detail'].replace('|', '/')} |" for c in CHECKS]
    markdown = "\n".join(rows) + "\n"
    with out_md.open("x", encoding="utf-8") as stream:
        stream.write(markdown)
    LATEST_JSON.write_text(content + "\n", encoding="utf-8")
    LATEST_MD.write_text(markdown, encoding="utf-8")
    return out_md, out_json


def main():
    head = cmd(["git", "rev-parse", "HEAD"])
    run_id = datetime.now(IST).strftime("%Y%m%dT%H%M%S") + "-" + secrets.token_hex(4)
    started_at = now_ist()
    image_id = None
    image_origin = f"friend/phase2-k8s@{head[:7]}"
    held = False
    cluster_started = False
    forwards = []
    try:
        if not KIND.is_file() or not HELM.is_file():
            raise RuntimeError("verified kind.exe and helm.exe are required in D:\\eAI\\tools")
        if not is_free():
            raise RuntimeError("the shared Docker lock is occupied")
        if cmd(["docker", "ps", "--filter", "label=com.docker.compose.project=eai",
                "--format", "{{.ID}}"]):
            raise RuntimeError("the Compose stack is running")
        if "eai" in cmd([KIND, "get", "clusters"]).splitlines():
            raise RuntimeError("kind cluster eai already exists")
        available = free_memory_gb()
        if available < 6:
            raise RuntimeError(f"only {available:.2f} GiB available; kind requires about 6 GiB")
        try:
            take("codex", "kind e2e", image_origin)
        except SystemExit:
            raise RuntimeError("could not acquire shared Docker lock") from None
        held = True
        check("preflight", True, f"Compose stopped, no eai kind cluster, {available:.2f} GiB free")

        cluster_started = True
        cmd([KIND, "create", "cluster", "--config", "deploy/kind/kind-cluster.yaml", "--name", "eai"], timeout=1200)
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
        cmd([KUBECTL, "-n", "monitoring", "rollout", "status", "deployment/prometheus-server", "--timeout=300s"])
        check("prometheus", True, f"chart {PROM_CHART} Ready")

        cmd([KUBECTL, "create", "namespace", "shop"])
        manifest = urllib.request.urlopen(MANIFEST, timeout=60).read()
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

        cmd(["docker", "build", "-t", "eai/eternalai:k8s-dev", "-f", "eternalai/Dockerfile", "."], timeout=1800)
        image_id = cmd(["docker", "image", "inspect", "--format", "{{.Id}}", "eai/eternalai:k8s-dev"])
        cmd([KIND, "load", "docker-image", "eai/eternalai:k8s-dev", "--name", "eai"], timeout=900)
        check("brain_image", True, f"eai/eternalai:k8s-dev {image_id} built from {head[:7]}")
        cmd([KUBECTL, "create", "namespace", "eternalai"])
        token = secrets.token_urlsafe(32)
        secret_manifest = {"apiVersion": "v1", "kind": "Secret",
                           "metadata": {"name": "eai-e2e-approval", "namespace": "eternalai"},
                           "stringData": {"token": token}}
        cmd([KUBECTL, "apply", "-f", "-"], input_text=json.dumps(secret_manifest))
        cmd([HELM, "install", "eternalai", "deploy/helm/eternalai", "-n", "eternalai",
             "--set", "approvalToken.existingSecret=eai-e2e-approval"], timeout=300)
        cmd([KUBECTL, "-n", "eternalai", "rollout", "status", "deployment/eternalai", "--timeout=300s"])
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
    except Exception as exc:
        check("aborted", False, type(exc).__name__)
    finally:
        for forward in forwards:
            forward.terminate()
            try:
                forward.wait(timeout=5)
            except subprocess.TimeoutExpired:
                forward.kill()
        if cluster_started:
            try:
                cmd([HELM, "uninstall", "eternalai", "-n", "eternalai"], timeout=120)
            except Exception:
                pass
            try:
                cmd([KIND, "delete", "cluster", "--name", "eai"], timeout=600)
                check("teardown", True, "only the eai kind cluster removed")
            except Exception as exc:
                check("teardown", False, type(exc).__name__)
        if held:
            try:
                cmd(["docker", "compose", "-p", "eai", "stop"], timeout=120)
            except Exception as exc:
                check("compose_stopped", False, type(exc).__name__)
            try:
                release("codex", image_origin)
                check("lock_release", True, "atomic owner file released")
            except (Exception, SystemExit) as exc:
                check("lock_release", False, type(exc).__name__)
        write_results(head, run_id, started_at, image_id)
    return 0 if CHECKS and all(item["result"] == "PASS" for item in CHECKS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
