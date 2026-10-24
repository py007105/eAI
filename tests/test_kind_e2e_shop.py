"""scripts/kind_e2e.py --target shop: pure helpers on small inputs written here (no Docker, kind or cluster)."""
import json

import pytest
import yaml

from scripts import kind_e2e as k

COMPOSE = k.ROOT / "docker-compose.yml"


def test_default_target_is_our_shop_and_boutique_stays_available():
    assert k.parse_args([]).target == "shop"
    assert k.parse_args(["--target", "boutique"]).target == "boutique"
    with pytest.raises(SystemExit):
        k.parse_args(["--target", "other"])


def test_image_builds_follow_docker_compose():
    builds = {b["tag"]: b for b in k.image_builds(COMPOSE)}
    assert set(builds) == {"eai/web:v1", "eai/orders:v1", "eai/payments:v1", "eai/inventory:v1",
                           f"eai/{k.BAD_SERVICE}:v3-bad", "eai/loadgen:v1", k.BRAIN_IMAGE}
    assert builds["eai/web:v1"] == {"tag": "eai/web:v1", "context": "./app", "dockerfile": None,
                                    "args": {"SERVICE": "web", "VERSION": "v1", "RELEASE_SEQ": "1"}}
    bad = builds[f"eai/{k.BAD_SERVICE}:v3-bad"]["args"]
    assert bad["RELEASE"] == "bad" and bad["SERVICE"] == k.BAD_SERVICE and bad["RELEASE_SEQ"] == "3"
    assert builds["eai/loadgen:v1"]["context"] == "./loadgen"
    brain = builds[k.BRAIN_IMAGE]
    assert brain["dockerfile"] == "eternalai/Dockerfile" and brain["context"] == "." and k.BRAIN_IMAGE != "eai/eternalai:v2"


def test_build_command():
    cmd = k.build_command({"tag": "eai/web:v1", "context": "./app", "dockerfile": None,
                           "args": {"VERSION": "v1", "SERVICE": "web"}})
    assert cmd == ["docker", "build", "-t", "eai/web:v1", "--build-arg", "SERVICE=web",
                   "--build-arg", "VERSION=v1", "./app"]
    cmd = k.build_command({"tag": "b", "context": ".", "dockerfile": "eternalai/Dockerfile", "args": {}})
    assert cmd == ["docker", "build", "-t", "b", "-f", "eternalai/Dockerfile", "."]


def test_fault_services_exist_in_the_shop_manifest():
    deployments = {d["metadata"]["name"]: d for d in yaml.safe_load_all(k.SHOP_MANIFEST.read_text(encoding="utf-8"))
                   if d and d["kind"] == "Deployment" and d["metadata"]["namespace"] == "shop"}
    for name in (k.CRASH_SERVICE, k.BAD_SERVICE, k.SCALE_SERVICE):
        assert name in deployments and name in k.SHOP_SERVICES
        # `kubectl set image deployment/<s> <s>=...` needs the container to be named like the service
        assert deployments[name]["spec"]["template"]["spec"]["containers"][0]["name"] == name


def pod(phase="Running", ready=True, running=True, deleting=False, cid="containerd://abc123"):
    meta = {"name": "inventory-1"}
    if deleting:
        meta["deletionTimestamp"] = "2026-10-24T10:00:00Z"
    state = {"running": {"startedAt": "x"}} if running else {"waiting": {"reason": "ContainerCreating"}}
    return {"metadata": meta, "status": {"phase": phase, "containerStatuses": [
        {"ready": ready, "state": state, "containerID": cid}]}}


def test_running_container_id_only_for_ready_running_pods():
    assert k.running_container_id(pod()) == "abc123"
    assert k.running_container_id(pod(ready=False)) is None
    assert k.running_container_id(pod(running=False)) is None
    assert k.running_container_id(pod(deleting=True)) is None
    assert k.running_container_id(pod(phase="Pending")) is None


def test_process_pid_refuses_init():
    assert k.process_pid({"info": {"pid": 4242}}) == 4242
    with pytest.raises(ValueError):
        k.process_pid({"info": {"pid": 1}})
    with pytest.raises(ValueError):
        k.process_pid({"info": {"pid": 0}})


def test_automatic_actions_are_the_brains_successful_calls_after_the_fault():
    audit = [{"t": 99, "service": "inventory", "runbook": "restart_service", "ok": True, "actor": "engine"},
             {"t": 101, "service": "inventory", "runbook": "restart_service", "ok": True, "actor": "kind-e2e"},
             {"t": 102, "service": "inventory", "runbook": "restart_service", "ok": False, "actor": "engine"},
             {"t": 103, "service": "web", "runbook": "restart_service", "ok": True, "actor": "engine"},
             {"t": 104, "service": "inventory", "runbook": "restart_service", "ok": True, "actor": "engine"}]
    assert [a["t"] for a in k.automatic_actions(audit, "inventory", "restart_service", 100)] == [104]


def test_actions_since_ignores_verification_and_older_calls():
    audit = [{"t": 5, "service": "payments", "runbook": "rollback_release"},
             {"t": 11, "service": "payments", "runbook": "verification"},
             {"t": 12, "service": "orders", "runbook": "restart_service"},
             {"t": 13, "service": "payments", "runbook": "rollback_release"}]
    assert [a["t"] for a in k.actions_since(audit, "payments", 10)] == [13]


def test_incident_helpers():
    incidents = [
        {"id": "a", "status": "recovered", "opened_t": 50, "verification": {"outcome": "recovered"},
         "actions": [{"service": "inventory", "runbook_id": "restart_service"}]},
        {"id": "b", "status": "verifying", "opened_t": 120, "verification": None,
         "actions": [{"service": "inventory", "runbook_id": "restart_service"}]},
        {"id": "c", "status": "recovered", "opened_t": 130, "verification": {"outcome": "recovered"},
         "actions": [{"service": "inventory", "runbook_id": "restart_service"}]},
        {"id": "d", "status": "awaiting_approval", "opened_t": 140, "verification": None, "actions": []}]
    assert [i["id"] for i in k.active_incidents(incidents)] == ["b", "d"]
    assert k.incident_with_action(incidents, "inventory", "restart_service", 100)["id"] == "c"
    assert k.incident_with_action(incidents, "inventory", "rollback_release", 0) is None


def deployment(desired=1, ready=1, updated=1, replicas=1, generation=2, observed=2, image="eai/payments:v1"):
    return {"metadata": {"generation": generation},
            "spec": {"replicas": desired, "template": {"spec": {"containers": [{"name": "payments", "image": image}]}}},
            "status": {"readyReplicas": ready, "updatedReplicas": updated, "replicas": replicas,
                       "observedGeneration": observed}}


def test_deployment_ready_and_image():
    assert k.deployment_ready(deployment())
    assert not k.deployment_ready(deployment(ready=0))
    assert not k.deployment_ready(deployment(replicas=2))          # an old pod is still there (rollout not done)
    assert not k.deployment_ready(deployment(observed=1))
    assert k.deployment_ready(deployment(desired=2, ready=2, updated=2, replicas=2), replicas=2)
    assert not k.deployment_ready(deployment(), replicas=2)
    assert k.deployment_image(deployment(image="eai/payments:v3-bad"), "payments") == "eai/payments:v3-bad"
    assert k.deployment_image(deployment(), "other") is None


def test_shop_results_are_execution_specific_and_say_live_only_when_all_pass(monkeypatch, tmp_path):
    monkeypatch.setattr(k, "ROOT", tmp_path)
    monkeypatch.setattr(k, "SHOP_LATEST_MD", tmp_path / "docs/results/k8s_e2e.md")
    monkeypatch.setattr(k, "SHOP_LATEST_JSON", tmp_path / "results/live-checks/kind_e2e_shop.json")
    monkeypatch.setattr(k, "CHECKS", [{"check": "auto_restart", "result": "PASS", "detail": "x", "t": "t"}])
    md, raw = k.write_results("abc", "run-1", "start", "sha256:img", target="shop",
                              configuration={"target": "shop"}, branch="team/k8s-rajat")
    data = json.loads(raw.read_text(encoding="utf-8"))
    assert md.name == "kind_e2e_shop_run-1.md" and raw.name == "kind_e2e_shop_run-1.json"
    assert data["target"] == "shop" and data["branch"] == "team/k8s-rajat" and data["image"]["id"] == "sha256:img"
    assert "**verified live**" in md.read_text(encoding="utf-8")
    assert k.SHOP_LATEST_MD.read_text(encoding="utf-8") == md.read_text(encoding="utf-8")
    monkeypatch.setattr(k, "CHECKS", [{"check": "auto_restart", "result": "FAIL", "detail": "x", "t": "t"}])
    md2, _ = k.write_results("abc", "run-2", "start", None, target="shop", configuration={"target": "shop"})
    assert "verified live**" not in md2.read_text(encoding="utf-8")
    assert "live run with failures" in md2.read_text(encoding="utf-8")
    with pytest.raises(FileExistsError):
        k.write_results("abc", "run-2", "start", None, target="shop", configuration={})


def test_shop_configuration_hashes_the_committed_inputs():
    conf = k.shop_configuration()
    assert conf["shop_manifest_sha256"] == k.file_hash(k.SHOP_MANIFEST)
    assert conf["prometheus_manifest_sha256"] == k.file_hash(k.SHOP_PROMETHEUS)
    assert conf["shop_values_sha256"] == k.file_hash(k.SHOP_VALUES)
    assert conf["mode_final"] == "autopilot"


def test_preflight_refuses_without_tools(monkeypatch, tmp_path):
    monkeypatch.setattr(k, "KIND", tmp_path / "kind.exe")
    monkeypatch.setattr(k, "HELM", tmp_path / "helm.exe")
    with pytest.raises(RuntimeError, match="kind.exe and helm.exe"):
        k.preflight("team/k8s-rajat@abc")
