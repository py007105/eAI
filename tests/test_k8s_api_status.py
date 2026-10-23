"""The status endpoint exposes whether Kubernetes discovery used a static graph."""

from fastapi.testclient import TestClient

from eternalai import api, config
from tests.test_autopilot_path import make_engine


def test_status_exposes_topology_fallback_without_changing_model_fallbacks(monkeypatch):
    engine = make_engine("watch-only", "orders", "down", monkeypatch)
    engine.models_loaded = {"detectors": False, "classifier": True, "ranker": True}
    engine.det_meta = engine.cls_meta = engine.rank_meta = None
    monkeypatch.setattr(api, "engine", engine)
    client = TestClient(api.app)

    monkeypatch.setattr(config, "TOPOLOGY_FALLBACK", True)
    fallback = client.get("/status").json()
    assert fallback["topology_fallback"] is True
    assert fallback["fallbacks_in_use"] == [key for key, loaded in engine.models_loaded.items() if not loaded]

    monkeypatch.setattr(config, "TOPOLOGY_FALLBACK", False)
    assert client.get("/status").json()["topology_fallback"] is False
