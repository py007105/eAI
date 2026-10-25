"""Generates dashboard/preview/sample_services.json and sample_incidents.json deterministically.

SYNTHETIC SAMPLE DATA ONLY: hand-made for the preview, never real telemetry. Running this script
twice produces byte-identical files (no randomness, no timestamps).
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent

N_TICKS = 60
INTERVAL_S = 2

NORMAL = {
    "lat_ratio": 1.0, "error_ratio": 0.0, "mem_share": 0.25, "rps_ratio": 1.0, "up_frac": 1.0,
    "mem_slope_share_per_min": 0.0, "restarts_in_window": 0, "deploys_3m": 0,
}


def _round4(features: dict) -> dict:
    return {k: (round(v, 4) if isinstance(v, float) else v) for k, v in features.items()}


def _inventory(i: int):
    f = dict(NORMAL)
    anomalous = i >= 20
    if anomalous:
        f["mem_share"] = 0.25 + 0.0125 * (i - 20)
        f["mem_slope_share_per_min"] = 0.375
    return _round4(f), anomalous


def _orders(i: int):
    f = dict(NORMAL)
    anomalous = i >= 30
    if anomalous:
        f["lat_ratio"] = 2.5
    return _round4(f), anomalous


def _web(i: int):
    f = dict(NORMAL)
    f["mem_share"] = 0.24
    if i >= 40:
        f["error_ratio"] = 0.05
    if 50 <= i <= 52:
        f["restarts_in_window"] = 1
    return _round4(f), False


def _payments(i: int):
    if 10 <= i <= 12:
        return None, False
    return _round4(dict(NORMAL)), False


def _score(anomalous: bool) -> float:
    return 0.75 if anomalous else 0.40


def _build_tick(i: int) -> dict:
    services = {}
    for svc_name, builder in (("inventory", _inventory), ("orders", _orders), ("web", _web), ("payments", _payments)):
        features, anomalous = builder(i)
        entry = {"anomalous": anomalous, "score": _score(anomalous)}
        if features is not None:
            entry["features"] = features
        services[svc_name] = entry
    return {"t": i * INTERVAL_S, "services": services}


def build_services_doc() -> dict:
    return {
        "label": "SYNTHETIC SAMPLE DATA - hand-made, not telemetry",
        "interval_s": INTERVAL_S,
        "ticks": [_build_tick(i) for i in range(N_TICKS)],
    }


def build_incidents_doc() -> dict:
    return {
        "label": "SYNTHETIC SAMPLE DATA - hand-made, not telemetry",
        "incidents": [
            {"id": "s1", "status": "recovered", "opened_t": 1000, "closed_t": 1029,
             "actions": [{"t": 1004, "runbook_id": "restart_service", "service": "web", "verdict": "execute",
                          "executed": True, "executed_t": 1006}],
             "verification": {"outcome": "recovered", "t": 1029, "success_rate": 1.0}},
            {"id": "s2", "status": "recovered", "opened_t": 2000, "closed_t": 2040,
             "actions": [{"t": 2010, "runbook_id": "recreate_container", "service": "web",
                          "verdict": "needs_approval", "executed": True, "executed_t": 2012}],
             "verification": {"outcome": "recovered", "t": 2040, "success_rate": 1.0}},
            {"id": "s3", "status": "escalated", "opened_t": 2100, "closed_t": 2130,
             "actions": [{"t": 2105, "runbook_id": "rollback_release", "service": "orders",
                          "verdict": "expired_unapproved", "executed": False}],
             "verification": None},
            {"id": "s4", "status": "awaiting_approval", "opened_t": 3000, "closed_t": None,
             "actions": [{"t": 3006, "runbook_id": "restart_service", "service": "payments",
                          "verdict": "needs_approval", "executed": False}],
             "verification": None},
        ],
    }


def main() -> None:
    (HERE / "sample_services.json").write_text(
        json.dumps(build_services_doc(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (HERE / "sample_incidents.json").write_text(
        json.dumps(build_incidents_doc(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
