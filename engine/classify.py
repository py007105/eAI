"""Fault classifier with calibrated probabilities and an explicit abstain path.

The model is a gradient-boosted classifier (NaN-aware) trained on windows from live evaluator
runs, calibrated on held-out runs. If the best calibrated probability is below the abstain
threshold the answer is "insufficient_evidence" (never a forced guess), which is also how
unseen fault types are meant to surface.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

CLASSES = ["healthy", "down", "latency_spike", "error_spike", "memory_leak", "disk_fill", "bad_deploy"]
ABSTAIN = "insufficient_evidence"

# Deterministic cause -> candidate runbooks (first is the default). The LLM may only choose among
# these; the policy engine still decides whether anything runs.
CAUSE_RUNBOOKS = {
    "down": ["restart_service", "recreate_container"],
    "memory_leak": ["recreate_container", "restart_service"],
    "disk_fill": ["clear_temp_path"],
    "bad_deploy": ["rollback_release"],
    "error_spike": ["restart_service"],
    "latency_spike": ["restart_service"],
}


@dataclass
class Prediction:
    label: str
    confidence: float           # calibrated probability of `label` (not an anomaly score)
    probs: dict[str, float]
    abstained: bool
    reason: str = ""            # "" | "low_confidence" | "novel"
    novelty: float | None = None


class FaultClassifier:
    """Calibrated classifier plus a novelty gate. It abstains when the window is far from every known training window
    (the confidence alone cannot tell: it labelled a never-seen fault with high confidence) or when confidence is low."""

    def __init__(self, model, features: list[str], classes: list[str], abstain_below: float, gate=None):
        self.model, self.features, self.classes, self.abstain_below = model, features, classes, abstain_below
        self.gate = gate

    def predict(self, feats: dict) -> Prediction:
        x = np.array([[feats.get(f, np.nan) for f in self.features]], dtype=float)
        p = self.model.predict_proba(x)[0]
        probs = {c: float(v) for c, v in zip(self.classes, p)}
        best = max(probs, key=probs.get)
        nov = self.gate.distance_of(feats) if self.gate is not None else None
        if self.gate is not None and nov > self.gate.threshold_:
            return Prediction(ABSTAIN, probs[best], probs, True, "novel", nov)
        if probs[best] < self.abstain_below:
            return Prediction(ABSTAIN, probs[best], probs, True, "low_confidence", nov)
        return Prediction(best, probs[best], probs, False, "", nov)


def rule_diagnose(feats: dict) -> str:
    """Simple threshold rules (no learning). Used only as an evaluation baseline."""
    g = lambda k: feats.get(k, np.nan)
    if g("up_frac") == 0 or np.isnan(g("up_frac")) and np.isnan(g("lat_ratio")):
        return "down"
    if g("mem_share") > 0.8 or g("mem_slope_share_per_min") > 0.05:
        return "memory_leak"
    if g("error_ratio") > 0.2:
        return "error_spike"
    if g("lat_ratio") > 3:
        return "latency_spike"
    return "healthy"
