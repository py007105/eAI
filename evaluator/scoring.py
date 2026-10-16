"""Score one run: EternalAI's incident records versus the private ground truth.

Incident contract (what EternalAI exposes at GET /incidents):
  id, opened_t, closed_t, status, services, ranking[{service,score}], likely_cause, abstained,
  actions[{t,runbook_id,service,verdict,executed}], verification{outcome,t}|null
"""
from __future__ import annotations

HEALTHY = {"traffic_surge", "good_deploy"}


def score_run(truth: dict, incidents: list[dict], failed_pct: float | None, t_end: float) -> dict:
    t0, svc, scen = truth["t_inject"], truth["target"], truth["scenario"]
    inc = sorted((i for i in incidents if i["opened_t"] >= t0 - 1), key=lambda i: i["opened_t"])
    actions = [a for i in inc for a in i["actions"] if a["executed"]]
    out = {"run_id": truth["run_id"], "scenario": scen, "target": svc, "failed_request_pct": failed_pct,
           "incidents_opened": len(inc), "actions_executed": len(actions)}

    if scen in HEALTHY:
        out.update(detected=bool(inc), false_alerts=len(inc),
                   harmful_interventions=len(actions), diagnosis_top1=None, diagnosis_top3=None,
                   cause_correct=None, abstained_correctly=None, time_to_detect_s=None,
                   time_to_verified_recovery_s=None, recovered=None)
        return out

    first = inc[0] if inc else None
    out["detected"] = first is not None
    out["time_to_detect_s"] = round(first["opened_t"] - t0, 1) if first else None
    out["false_alerts"] = 0
    out["extra_incidents"] = max(len(inc) - 1, 0)
    if first:
        ranked = [r["service"] for r in first["ranking"]]
        out["diagnosis_top1"] = bool(ranked[:1] == [svc])
        out["diagnosis_top3"] = svc in ranked[:3]
        out["cause_correct"] = first["likely_cause"] == truth["expected_label"]
        out["abstained"] = bool(first["abstained"])
    else:
        out.update(diagnosis_top1=False, diagnosis_top3=False, cause_correct=False, abstained=False)
    if not truth["supported"]:  # unseen fault: the right behaviour is to say "insufficient evidence"
        out["abstained_correctly"] = bool(first and first["abstained"])
        out["cause_correct"] = None
    else:
        out["abstained_correctly"] = None
    # harmful = an executed action on a service that was not the injected target
    out["harmful_interventions"] = sum(a["service"] != svc for a in actions)
    ver = [i["verification"] for i in inc if i.get("verification")]
    rec = [v for v in ver if v["outcome"] == "recovered"]
    out["recovered"] = bool(rec)
    out["time_to_verified_recovery_s"] = round(min(v["t"] for v in rec) - t0, 1) if rec else None
    out["final_status"] = inc[-1]["status"] if inc else "undetected"
    out["window_s"] = round(t_end - t0, 1)
    return out


def aggregate(rows: list[dict]) -> dict:
    """Mean and spread per scenario. Numbers are computed from rows only; nothing is assumed."""
    import statistics as st
    by: dict[str, list[dict]] = {}
    for r in rows:
        by.setdefault(r["scenario"], []).append(r)

    def stat(vals):
        v = [x for x in vals if x is not None]
        if not v:
            return None
        return {"mean": round(st.mean(v), 2), "sd": round(st.pstdev(v), 2) if len(v) > 1 else 0.0, "n": len(v)}

    out = {}
    for s, rs in by.items():
        out[s] = {"runs": len(rs),
                  "detected": sum(bool(r["detected"]) for r in rs),
                  "time_to_detect_s": stat([r["time_to_detect_s"] for r in rs]),
                  "time_to_verified_recovery_s": stat([r["time_to_verified_recovery_s"] for r in rs]),
                  "failed_request_pct": stat([r["failed_request_pct"] for r in rs]),
                  "top1": sum(bool(r["diagnosis_top1"]) for r in rs if r["diagnosis_top1"] is not None),
                  "top3": sum(bool(r["diagnosis_top3"]) for r in rs if r["diagnosis_top3"] is not None),
                  "recovered": sum(bool(r["recovered"]) for r in rs if r["recovered"] is not None),
                  "false_alerts": sum(r["false_alerts"] for r in rs),
                  "harmful_interventions": sum(r["harmful_interventions"] for r in rs),
                  "abstained_correctly": sum(bool(r["abstained_correctly"]) for r in rs
                                             if r.get("abstained_correctly") is not None)}
    return out
