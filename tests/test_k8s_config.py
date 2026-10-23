from types import SimpleNamespace as NS
from unittest.mock import Mock

from eternalai import config


def test_load_topology_discovers_once_and_exposes_fallback(monkeypatch):
    with monkeypatch.context() as patch:
        patch.setenv("RUNTIME", "kubernetes")
        patch.setattr(config, "TOPOLOGY", {"web": []})
        patch.setattr(config, "SERVICES", ["web"])
        patch.setattr(config, "CALLERS", {"web": []})
        apps = Mock()
        apps.list_namespaced_deployment.return_value.items = [
            NS(metadata=NS(name="frontend", annotations={"eternalai.io/depends-on": "cartservice"})),
            NS(metadata=NS(name="cartservice", annotations={}))]
        assert config.load_topology(apps, ["shop"]) == {"frontend": ["cartservice"], "cartservice": []}
        assert config.SERVICES == ["frontend", "cartservice"]
        assert config.CALLERS["cartservice"] == ["frontend"]
        assert not config.TOPOLOGY_FALLBACK
        apps.list_namespaced_deployment.return_value.items = []
        config.load_topology(apps, ["shop"])
        assert config.TOPOLOGY_FALLBACK
        assert config.TOPOLOGY == config._STATIC_TOPOLOGY
