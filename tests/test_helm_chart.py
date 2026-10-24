import shutil
import subprocess
from pathlib import Path

import pytest
import yaml


CHART = Path(__file__).resolve().parents[1] / "deploy" / "helm" / "eternalai"


def render(*values):
    local_helm = Path(r"D:\eAI\tools\helm.exe")
    helm = shutil.which("helm") or (str(local_helm) if local_helm.is_file() else None)
    if not helm:
        pytest.skip("helm is not on PATH")
    result = subprocess.run([helm, "template", "eternalai", str(CHART), "-n", "eternalai", *values],
                            capture_output=True, text=True, check=True)
    return [item for item in yaml.safe_load_all(result.stdout) if item]


def test_watch_chart_is_namespaced_read_only_and_has_no_secret_data():
    manifests = render()
    assert "ClusterRole" not in [item["kind"] for item in manifests]
    assert "Secret" not in [item["kind"] for item in manifests]
    role = next(item for item in manifests if item["kind"] == "Role")
    assert role["metadata"]["namespace"] == "shop"
    assert role["rules"] == [
        {"apiGroups": ["apps"], "resources": ["deployments", "deployments/scale", "replicasets"],
         "verbs": ["get", "list", "watch"]},
        {"apiGroups": [""], "resources": ["pods", "events", "services"],
         "verbs": ["get", "list", "watch"]}]
    deployment = next(item for item in manifests if item["kind"] == "Deployment")
    env = {item["name"]: item for item in deployment["spec"]["template"]["spec"]["containers"][0]["env"]}
    assert env["RUNTIME"]["value"] == "kubernetes"
    assert env["METRICS_SOURCE"]["value"] == "kubernetes"
    assert "ETERNALAI_APPROVAL_TOKEN" not in env


def test_ask_chart_grants_exact_write_rules_but_reads_existing_token_only():
    manifests = render("--set", "mode=ask", "--set", "approvalToken.existingSecret=approval")
    role = next(item for item in manifests if item["kind"] == "Role")
    assert role["rules"] == [
        {"apiGroups": ["apps"], "resources": ["deployments", "deployments/scale", "replicasets"],
         "verbs": ["get", "list", "watch", "patch", "update"]},
        {"apiGroups": [""], "resources": ["pods", "events", "services"],
         "verbs": ["get", "list", "watch"]},
        {"apiGroups": [""], "resources": ["pods"], "verbs": ["delete"]}]
    assert all(item["kind"] != "Secret" for item in manifests)
    deployment = next(item for item in manifests if item["kind"] == "Deployment")
    env = {item["name"]: item for item in deployment["spec"]["template"]["spec"]["containers"][0]["env"]}
    assert env["ETERNALAI_APPROVAL_TOKEN"]["valueFrom"]["secretKeyRef"] == {
        "name": "approval", "key": "token"}


def test_shop_values_set_app_metrics_and_our_frontend():
    values = str(Path(__file__).resolve().parents[1] / "deploy" / "kind" / "shop" / "values-shop.yaml")
    manifests = render("-f", values)
    deployment = next(item for item in manifests if item["kind"] == "Deployment")
    container = deployment["spec"]["template"]["spec"]["containers"][0]
    env = {item["name"]: item.get("value") for item in container["env"]}
    assert env["KUBERNETES_METRICS"] == "app"
    assert env["KUBERNETES_FRONTEND_URL"] == "http://web.shop.svc.cluster.local:8000"
    assert env["PROMETHEUS_URL"] == "http://prometheus.monitoring.svc.cluster.local:9090"
    assert container["imagePullPolicy"] == "Never"
    assert env["ETERNALAI_APPROVAL_TTL_S"] == "900"
    default_env = {item["name"]: item.get("value") for item in next(
        item for item in render() if item["kind"] == "Deployment")["spec"]["template"]["spec"]["containers"][0]["env"]}
    assert default_env["KUBERNETES_METRICS"] == "cluster" and "KUBERNETES_FRONTEND_URL" not in default_env
    assert "ETERNALAI_APPROVAL_TTL_S" not in default_env
