from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest

from eternalai.drivers.base import NotSupported, UNSUPPORTED
from eternalai.drivers.k8s import KubernetesDriver
from eternalai.executor import ExecutionError


def obj(**kwargs):
    return NS(**kwargs)


@pytest.fixture
def driver(tmp_path):
    owner = obj(kind="Deployment", uid="deployment-uid")
    rs_owner = obj(kind="ReplicaSet", uid="rs-uid")
    deployment = obj(metadata=obj(uid="deployment-uid", annotations={"deployment.kubernetes.io/revision": "2"}),
                     spec=obj(replicas=1, selector=obj(match_labels={"app": "frontend"})))
    old_template = obj(metadata=obj(labels={"app": "frontend", "pod-template-hash": "old"}), spec=obj())
    old_rs = obj(metadata=obj(uid="rs-uid", owner_references=[owner],
                              annotations={"deployment.kubernetes.io/revision": "1"}),
                 spec=obj(template=old_template))
    pod = obj(metadata=obj(name="frontend-old", owner_references=[rs_owner]))
    apps = Mock()
    apps.read_namespaced_deployment.return_value = deployment
    apps.list_namespaced_replica_set.return_value.items = [old_rs]
    core = Mock()
    core.list_namespaced_pod.return_value.items = [pod]
    return KubernetesDriver("shop", ["shop"], apps=apps, core=core, audit_path=tmp_path / "audit.jsonl")


def test_recovery_actions_use_namespaced_apis_and_audit(driver):
    restart = driver.run("restart_service", "frontend", "operator", ["e1"], "unready")
    assert restart["ok"] and restart["restarted"] == "frontend"
    patch = driver.apps.patch_namespaced_deployment.call_args.args[2]
    assert "kubectl.kubernetes.io/restartedAt" in patch["spec"]["template"]["metadata"]["annotations"]
    assert driver.replicas("frontend") == 1
    assert driver.scale_to("frontend", 2)["replicas"] == 2
    driver.apps.patch_namespaced_deployment_scale.assert_called_once_with(
        "frontend", "shop", {"spec": {"replicas": 2}})
    assert driver.run("recreate_container", "frontend", "operator")["deleted_pod"] == "frontend-old"
    driver.core.delete_namespaced_pod.assert_called_once_with("frontend-old", "shop")
    assert driver.run("rollback_release", "frontend", "approver")["to_revision"] == 1
    template = driver.apps.patch_namespaced_deployment.call_args.args[2]["spec"]["template"]
    assert template.metadata.labels == {"app": "frontend"}
    assert len(driver.audit) == 5
    assert driver.audit_path.read_text().count("\n") == 5
    assert driver.audit[0]["actor"] == "operator" and driver.audit[0]["evidence_ids"] == ["e1"]


def test_namespace_allowlist_and_unsupported_operations_are_audited(driver):
    with pytest.raises(ExecutionError, match="PermissionError"):
        driver.run("restart_service", "kube-system/frontend", "operator")
    assert driver.apps.patch_namespaced_deployment.call_count == 0
    for operation in ("clear_temp_path", *UNSUPPORTED):
        with pytest.raises(NotSupported):
            if operation == "clear_temp_path":
                driver.run(operation, "frontend", "operator")
            else:
                getattr(driver, operation)("frontend")
    assert len(driver.audit) == 1 + 1 + len(UNSUPPORTED)
    assert all(not record["ok"] for record in driver.audit)


def test_refuse_pod_not_owned_by_target_deployment(driver):
    driver.apps.list_namespaced_replica_set.return_value.items = []
    with pytest.raises(ValueError, match="no matching Pod"):
        driver.delete_pod("frontend")
    driver.core.delete_namespaced_pod.assert_not_called()
    assert driver.audit[-1]["error"] == "ValueError"


def test_api_failure_is_audited_and_caught_by_engine_contract(driver):
    driver.apps.patch_namespaced_deployment.side_effect = RuntimeError("private API detail")
    with pytest.raises(ExecutionError, match="RuntimeError") as caught:
        driver.run("restart_service", "frontend", "operator")
    assert "private API detail" not in str(caught.value)
    assert driver.audit[-1]["error"] == "RuntimeError"
