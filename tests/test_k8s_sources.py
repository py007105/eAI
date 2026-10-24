from types import SimpleNamespace as NS
from unittest.mock import Mock

import httpx
import pytest

from eternalai.sources import make_sources
from eternalai.sources.k8s_metrics import KubernetesProm
from eternalai.sources.k8s_state import KubernetesView


def test_kubernetes_source_pair_requires_rulebook_namespace(monkeypatch):
    monkeypatch.setattr("eternalai.sources.rulebook.load", lambda: NS(namespaces=("shop",)))
    args = {"METRICS_SOURCE": "kubernetes", "KUBERNETES_NAMESPACE": "shop", "PROMETHEUS_URL": "http://prom"}
    prom, view = make_sources(args, apps=Mock(), core=Mock(), prom_client=httpx.Client(base_url="http://prom"))
    assert isinstance(prom, KubernetesProm) and isinstance(view, KubernetesView)
    assert prom.namespace == view.namespace == "shop"
    with pytest.raises(PermissionError):
        make_sources({**args, "KUBERNETES_NAMESPACE": "kube-system"})


def test_app_metrics_profile_uses_the_docker_queries_on_kubernetes(monkeypatch):
    from eternalai.collector import Prom
    monkeypatch.setattr("eternalai.sources.rulebook.load", lambda: NS(namespaces=("shop",)))
    args = {"METRICS_SOURCE": "kubernetes", "KUBERNETES_NAMESPACE": "shop",
            "PROMETHEUS_URL": "http://prometheus.monitoring.svc:9090", "KUBERNETES_METRICS": "app"}
    prom, view = make_sources(args, apps=Mock(), core=Mock())
    assert type(prom) is Prom and not isinstance(prom, KubernetesProm)
    assert str(prom.c.base_url).rstrip("/") == "http://prometheus.monitoring.svc:9090"
    assert isinstance(view, KubernetesView) and view.namespace == "shop"
    with pytest.raises(PermissionError):                       # the namespace rule still applies
        make_sources({**args, "KUBERNETES_NAMESPACE": "kube-system"})
    with pytest.raises(ValueError):                            # a token is never silently dropped
        make_sources({**args, "PROMETHEUS_TOKEN": "x"}, apps=Mock(), core=Mock())
    with pytest.raises(ValueError):
        make_sources({**args, "KUBERNETES_METRICS": "other"}, apps=Mock(), core=Mock())


def test_cluster_profile_is_the_default(monkeypatch):
    monkeypatch.setattr("eternalai.sources.rulebook.load", lambda: NS(namespaces=("shop",)))
    args = {"METRICS_SOURCE": "kubernetes", "KUBERNETES_NAMESPACE": "shop", "PROMETHEUS_URL": "http://prom"}
    prom, _ = make_sources(args, apps=Mock(), core=Mock(), prom_client=httpx.Client(base_url="http://prom"))
    assert isinstance(prom, KubernetesProm)


def test_docker_path_is_unchanged_and_ignores_kubernetes_metrics(monkeypatch):
    """KUBERNETES_METRICS is read only on the Kubernetes path: the default (Docker) runtime still gets collector.Prom
    with its default URL and a DockerView, with or without the variable, and the rulebook is not consulted."""
    from eternalai import config
    from eternalai.collector import Prom

    class StubView:                       # DockerView would connect to Docker; only its selection is tested here
        pass

    def no_rulebook():
        raise AssertionError("the Docker path must not read the rulebook")

    monkeypatch.setattr("eternalai.sources.DockerView", StubView)
    monkeypatch.setattr("eternalai.sources.rulebook.load", no_rulebook)
    for env in ({}, {"RUNTIME": "docker"}, {"KUBERNETES_METRICS": "app"},
                {"RUNTIME": "docker", "KUBERNETES_METRICS": "app", "PROMETHEUS_URL": "http://elsewhere:9090"}):
        prom, view = make_sources(env)
        assert type(prom) is Prom and isinstance(view, StubView)
        assert str(prom.c.base_url).rstrip("/") == config.PROMETHEUS_URL.rstrip("/")
