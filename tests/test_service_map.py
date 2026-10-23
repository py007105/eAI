from types import SimpleNamespace as NS
from unittest.mock import Mock

from eternalai.sources.service_map import callers, discover_topology


def deployment(name, depends=None):
    return NS(metadata=NS(name=name, annotations={"eternalai.io/depends-on": depends} if depends else {}))


def test_annotation_graph_and_callers():
    apps = Mock()
    apps.list_namespaced_deployment.return_value.items = [
        deployment("frontend", "cartservice, checkoutservice, cartservice"),
        deployment("cartservice", "redis-cart"), deployment("checkoutservice"), deployment("redis-cart")]
    graph, fallback = discover_topology(apps, ["shop"])
    assert not fallback
    assert graph == {"frontend": ["cartservice", "checkoutservice"],
                     "cartservice": ["redis-cart"], "checkoutservice": [], "redis-cart": []}
    assert callers(graph)["cartservice"] == ["frontend"]
    apps.list_namespaced_deployment.assert_called_once_with("shop")


def test_empty_or_failed_discovery_uses_static_fallback():
    apps = Mock()
    apps.list_namespaced_deployment.return_value.items = []
    assert discover_topology(apps, ["shop"], {"web": []}) == ({"web": []}, True)
    apps.list_namespaced_deployment.side_effect = RuntimeError("API unavailable")
    assert discover_topology(apps, ["shop"], {"web": []}) == ({"web": []}, True)
