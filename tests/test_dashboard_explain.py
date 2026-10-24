import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "dashboard"))
from explain_words import explain_service  # noqa: E402

SAMPLES = Path(__file__).resolve().parents[1] / "dashboard" / "preview" / "sample_services.json"


def _tick(i):
    data = json.loads(SAMPLES.read_text(encoding="utf-8"))
    return data["ticks"][i]["services"]


def test_inventory_memory_leak_sentence_at_tick_59():
    features = _tick(59)["inventory"]["features"]
    assert explain_service("inventory", features, "en") == [
        "inventory memory is at 74% of its limit. It is rising about 38% of the limit per minute."
    ]


def test_orders_slow_sentence_at_tick_59():
    features = _tick(59)["orders"]["features"]
    assert explain_service("orders", features, "en") == ["orders responds 2.5 times slower than normal."]


def test_normal_service_gives_empty_list():
    features = _tick(0)["web"]["features"]
    assert explain_service("web", features, "en") == []


def test_missing_or_nan_features_give_no_sentence():
    assert explain_service("x", None, "en") == []
    assert explain_service("x", {}, "en") == []
    assert explain_service("x", {"lat_ratio": float("nan"), "mem_share": float("inf")}, "en") == []


def test_score_and_z_values_never_shown():
    features = {"score": 0.4242, "lat_z": 9.87, "lat_ratio": 2.0, "up_frac": 1.0}
    sentences = explain_service("svc", features, "en")
    joined = " ".join(sentences)
    assert "0.4242" not in joined
    assert "9.87" not in joined


def test_hindi_output_uses_hindi_templates():
    inv = explain_service("inventory", _tick(59)["inventory"]["features"], "hi")
    ordr = explain_service("orders", _tick(59)["orders"]["features"], "hi")
    assert inv == ["inventory की मेमोरी सीमा के 74% पर है। यह हर मिनट सीमा का लगभग 38% बढ़ रही है।"]
    assert ordr == ["orders सामान्य से 2.5 गुना धीमा है।"]
    # cross-check: Hindi differs from English for the same inputs
    assert inv != explain_service("inventory", _tick(59)["inventory"]["features"], "en")
