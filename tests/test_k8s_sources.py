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
