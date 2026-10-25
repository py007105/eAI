"""Infrastructure twin and incident knowledge graph, built from existing engine state and stored investigations.
No LLM call: both are plain reads, safe to poll."""
from __future__ import annotations

from .. import config


def twin(engine, inv) -> dict:
    with engine.lock:
        incidents = [i.public() for i in engine.incidents]
    active = [i for i in incidents if i["status"] in ("open", "awaiting_approval", "executing", "verifying")]
    last_by_service: dict = {}
    for rid, rec in (inv.records if inv else {}).items():
        f = rec.get("finding") or {}
        s = f.get("root_cause_service")
        if s and rec.get("status") == "completed":
            if s not in last_by_service or rec.get("finished_t", 0) > last_by_service[s]["finished_t"]:
                last_by_service[s] = {"incident_id": rid, "fault": f.get("fault"), "confidence": f.get("confidence"),
                                      "finished_t": rec.get("finished_t", 0)}
    services = {}
    for s in config.SERVICES:
        v = (engine.latest or {}).get(s) or {}
        st = v.get("state") or {}
        services[s] = {"score": v.get("score"), "anomalous": v.get("anomalous"),
                       "running": st.get("running") if isinstance(st, dict) else None,
                       "health": ("unknown" if not v else "down" if isinstance(st, dict) and st.get("running") is False
                                  else "anomalous" if v.get("anomalous") else "healthy"),
                       "calls": config.TOPOLOGY.get(s, []),
                       "active_incidents": [i["id"] for i in active if s in (i.get("services") or [])],
                       "last_agent37_investigation": last_by_service.get(s)}
    return {"services": services, "topology": config.TOPOLOGY,
            "active_incidents": [{"id": i["id"], "status": i["status"], "services": i["services"],
                                  "likely_cause": i.get("likely_cause")} for i in active],
            "source": "EternalAI telemetry (/services) and incidents; no LLM call"}


def graph(engine, inv) -> dict:
    """Nodes and typed edges. A diagnosis is always SUSPECTED_CAUSE (model or agent), never confirmed."""
    nodes, edges = {}, []

    def node(nid, kind, label, **kw):
        nodes.setdefault(nid, {"id": nid, "kind": kind, "label": label, **kw})

    for s in config.SERVICES:
        node(f"svc:{s}", "service", s)
    for a, bs in config.TOPOLOGY.items():
        for b in bs:
            edges.append({"from": f"svc:{a}", "to": f"svc:{b}", "type": "DEPENDS_ON", "source": "topology"})
    with engine.lock:
        incidents = {i.id: i.public() for i in engine.incidents}
    records = dict(inv.records) if inv else {}
    for iid in list(incidents) + [r for r in records if r not in incidents]:
        inc = incidents.get(iid)
        snap = inc or (records[iid].get("incident_snapshot") or {})
        src = "live engine" if inc else "investigation record"
        node(f"inc:{iid}", "incident", iid, status=snap.get("status"), source=src, t=(inc or {}).get("opened_t"))
        for s in snap.get("services") or []:
            edges.append({"from": f"inc:{iid}", "to": f"svc:{s}", "type": "AFFECTED_BY", "source": src})
        if snap.get("likely_cause"):
            node(f"fault:{snap['likely_cause']}", "fault", snap["likely_cause"])
            edges.append({"from": f"inc:{iid}", "to": f"fault:{snap['likely_cause']}", "type": "SUSPECTED_CAUSE",
                          "source": "EternalAI classifier (model prediction)"})
        if inc:
            if inc.get("evidence"):
                edges.append({"from": f"inc:{iid}", "to": f"inc:{iid}", "type": "HAS_EVIDENCE",
                              "count": len(inc["evidence"]), "source": "live engine"})
            for a in inc.get("actions") or []:
                aid = f"act:{iid}:{a.get('runbook_id')}@{a.get('service')}"
                node(aid, "action", f"{a.get('runbook_id')} on {a.get('service')}", verdict=a.get("verdict"))
                edges.append({"from": f"inc:{iid}", "to": aid, "type": "EXECUTED_ACTION" if a.get("executed") else "PROPOSED_ACTION",
                              "verdict": a.get("verdict"), "approved_by": a.get("approved_by"), "source": "EternalAI policy/executor"})
            outcome = (inc.get("verification") or {}).get("outcome")
            if outcome:
                node(f"out:{iid}", "outcome", outcome)
                edges.append({"from": f"inc:{iid}", "to": f"out:{iid}", "type": "VERIFIED_OUTCOME",
                              "source": "EternalAI checkout probes"})
        rec = records.get(iid) or {}
        f = rec.get("finding")
        if f:
            node(f"fault:{f['fault']}", "fault", f["fault"])
            edges.append({"from": f"inc:{iid}", "to": f"fault:{f['fault']}", "type": "SUSPECTED_CAUSE",
                          "source": "Agent37 investigation", "confidence": f.get("confidence")})
            if f.get("suggested_runbook") and f["suggested_runbook"] != "none":
                aid = f"rec:{iid}:{f['suggested_runbook']}@{f['root_cause_service']}"
                node(aid, "recommendation", f"{f['suggested_runbook']} on {f['root_cause_service']}",
                     policy=(rec.get("policy") or {}).get("verdict"))
                edges.append({"from": f"inc:{iid}", "to": aid, "type": "PROPOSED_ACTION", "source": "Agent37 (advisory)",
                              "policy_verdict": (rec.get("policy") or {}).get("verdict")})
    return {"nodes": list(nodes.values()), "edges": edges,
            "note": "Causes are suspected (classifier or Agent37), never confirmed; outcomes come from checkout probes."}
