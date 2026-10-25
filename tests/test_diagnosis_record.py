"""v2 item B: the diagnosis details v1 discarded are recorded on the incident and reach its public form."""
from types import SimpleNamespace

from engine.classify import ABSTAIN, Prediction
from engine.engine import Engine, Incident


def engine(det=None, gate_threshold=1.0):
    e = Engine.__new__(Engine)
    e.classifier = SimpleNamespace(abstain_below=0.4, gate=SimpleNamespace(threshold_=gate_threshold))
    e.detectors = det
    return e


class FakeDetector:
    def out_of_range(self, feats):
        return ["mem_share"] if feats.get("mem_share", 0) > 0.26 else []


def test_abstention_keeps_top_class_probability_reason_and_novelty():
    p = Prediction(ABSTAIN, 0.99999839, {"down": 0.99999839, "healthy": 1e-6}, True, "novel", 1.37)
    rec = engine({"orders": FakeDetector()})._diagnosis_record("orders", p, {"mem_share": 0.3})
    assert rec["top_class"] == "down" and rec["top_probability"] == 0.999998
    assert rec["answered_label"] == ABSTAIN and rec["abstain_reason"] == "novel" and rec["novelty"] == 1.37
    assert rec["novelty_threshold"] == 1.0 and rec["abstain_below"] == 0.4 and rec["limits_exceeded"] == ["mem_share"]


def test_answered_prediction_has_no_abstain_reason_and_missing_detector_is_none():
    p = Prediction("down", 0.97, {"down": 0.97, "healthy": 0.03}, False, "", 0.2)
    rec = engine(det=None)._diagnosis_record("web", p, {})
    assert rec["abstain_reason"] is None and rec["limits_exceeded"] is None and rec["answered_label"] == "down"


def test_public_form_carries_the_diagnosis():
    inc = Incident("i", 1.0)
    inc.diagnosis = {"top_class": "down"}
    assert inc.public()["diagnosis"] == {"top_class": "down"}
    assert Incident("j", 1.0).public()["diagnosis"] is None
