"""G5 controlled stimulus: the threshold comes only from measured scores, and an inseparable fault is never forced."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import live_check_g5 as g5  # noqa: E402


def test_sustained_level_needs_consecutive_samples():
    assert g5.sustained_level([0.5, 0.9, 0.5, 0.5], 2) == 0.5          # a single spike does not count
    assert g5.sustained_level([0.5, 0.8, 0.85, 0.9, 0.5], 3) == 0.8
    assert g5.sustained_level([0.9], 3) is None


def test_threshold_is_between_healthy_max_and_sustained_fault_level():
    t = g5.threshold_from([0.40, 0.42, 0.45], [0.44, 0.60, 0.62, 0.61, 0.63, 0.50], k=4)
    assert t["separable"] and t["healthy_max"] == 0.45 and t["fault_sustained"] == 0.60
    assert t["healthy_max"] < t["threshold"] < t["fault_sustained"] and t["threshold"] == 0.525


def test_inseparable_or_missing_data_gives_no_threshold():
    assert not g5.threshold_from([0.40, 0.50], [0.49, 0.50, 0.505, 0.50], k=4)["separable"]   # within MIN_SEPARATION
    assert g5.threshold_from([], [0.9] * 5)["threshold"] is None
    assert g5.threshold_from([0.4], [0.9, 0.9])["threshold"] is None                          # too few fault samples


def test_substitution_changes_only_detector_data_for_the_target():
    code = g5.substitution_code(0.525)
    assert "detectors.joblib" in code and "'limits',{}" in code and "d['web'].threshold=0.525" in code
    assert "policy" not in code and "rulebook" not in code
