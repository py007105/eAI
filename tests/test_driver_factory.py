from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest

from eternalai.drivers import make_driver
from eternalai.drivers.docker import DockerDriver
from eternalai.drivers.k8s import KubernetesDriver


def test_default_runtime_is_docker(monkeypatch):
    monkeypatch.setattr("eternalai.drivers.DockerDriver", Mock(return_value="docker sentinel"))
    assert make_driver(env={}) == "docker sentinel"


def test_kubernetes_requires_allowed_namespace(tmp_path):
    # The APIs are injected only to keep the unit test off the network.
    driver = make_driver(env={"RUNTIME": "kubernetes", "KUBERNETES_NAMESPACE": "shop"},
                         policy=NS(namespaces=("shop",)), apps=Mock(), core=Mock(),
                         audit_path=tmp_path / "audit.jsonl")
    assert isinstance(driver, KubernetesDriver)
    assert driver.namespace == "shop"
    with pytest.raises(PermissionError):
        make_driver(env={"RUNTIME": "kubernetes", "KUBERNETES_NAMESPACE": "kube-system"},
                    policy=NS(namespaces=("shop",)), apps=Mock(), core=Mock(),
                    audit_path=tmp_path / "audit.jsonl")


def test_unknown_runtime_fails_closed():
    with pytest.raises(ValueError, match="RUNTIME"):
        make_driver(env={"RUNTIME": "unknown"})
