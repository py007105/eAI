"""Pure rendering functions: backend JSON in, Plotly figures / Dash components out. No network here."""
from __future__ import annotations

import math
import time

import plotly.graph_objects as go
from dash import html
from dash_iconify import DashIconify

from labels import t
from theme import PALETTE, TEMPLATE

POS = {"web": (0.0, 0.5), "orders": (1.0, 0.5), "inventory": (2.0, 0.85), "payments": (2.0, 0.15)}


def icon(name, cls=""):
    return html.Span(DashIconify(icon=name, width=17), className=f"icon-circle {cls}")


def panel_title(icon_name, key, lang, cls=""):
    return html.H3([icon(icon_name, cls), t(key, lang)])


def node_state(svc: dict) -> str:
    if not svc:
        return "unknown"
    st = svc.get("state") or {}
    if st.get("running") is False or (svc.get("features") or {}).get("up_frac") == 0:
        return "down"
    return "anomalous" if svc.get("anomalous") else "healthy"


def service_map(services: dict, topology: dict, lang="en") -> go.Figure:
    col = {"healthy": PALETTE["ok"], "anomalous": PALETTE["warn"], "down": PALETTE["bad"], "unknown": PALETTE["muted"]}
    states = {s: node_state(services.get(s)) for s in topology}
    fig = go.Figure()
    for a, bs in topology.items():
        for b in bs:
            bad = states[a] != "healthy" and states[b] != "healthy"
            (x0, y0), (x1, y1) = POS[a], POS[b]
            fig.add_trace(go.Scatter(x=[x0, x1], y=[y0, y1], mode="lines", hoverinfo="skip", showlegend=False,
                                     line=dict(color=PALETTE["bad"] if bad else PALETTE["line"], width=5 if bad else 2,
                                               dash="solid" if bad else "dot")))
    xs, ys = zip(*(POS[s] for s in topology))
    fig.add_trace(go.Scatter(
        x=xs, y=ys, mode="markers+text", text=list(topology), textposition="bottom center", showlegend=False,
        marker=dict(size=46, color=[col[states[s]] for s in topology], line=dict(color="#ffffff", width=1),
                    opacity=.95),
        customdata=[[t(states[s], lang)] for s in topology],
        hovertemplate="%{text}: %{customdata[0]}<extra></extra>"))
    # soft glow behind the nodes
    fig.add_trace(go.Scatter(x=xs, y=ys, mode="markers", hoverinfo="skip", showlegend=False,
                             marker=dict(size=78, color=[col[states[s]] for s in topology], opacity=.18)))
    fig.update_layout(template=TEMPLATE, height=330, xaxis=dict(visible=False, range=[-.4, 2.4]),
                      yaxis=dict(visible=False, range=[-.1, 1.1]), margin=dict(l=10, r=10, t=10, b=10))
    return fig


def causes_fig(inc: dict | None, lang="en"):
    fig = go.Figure()
    if inc and inc.get("ranking"):
        r = inc["ranking"][:4]
        fig.add_trace(go.Bar(x=[x["score"] for x in r][::-1], y=[x["service"] for x in r][::-1], orientation="h",
                             marker=dict(color=[PALETTE["gold"] if i == 0 else PALETTE["violet"] for i in range(len(r))][::-1])))
    fig.update_layout(template=TEMPLATE, height=190, xaxis=dict(range=[0, 1], title="relative support"),
                      margin=dict(l=70, r=10, t=10, b=34))
    return fig


def margin_text(inc: dict | None, lang="en") -> str:
    if not inc or len(inc.get("ranking", [])) < 2:
        return ""
    r = inc["ranking"]
    return f"{t('uncertainty', lang)}: {r[0]['score'] - r[1]['score']:.2f}"


def forecast_fig(inc: dict | None, lang="en"):
    fig = go.Figure()
    f = (inc or {}).get("forecasts") or []
    if not f:
        return fig, False
    f = f[-1]
    share = f["share_of_limit_now"]
    # eta gives the time to the limit in seconds, so draw a straight projection from now to 100%
    lo, mid, hi = f["eta_earliest_s"], f["eta_s"], f["eta_latest_s"]
    fig.add_trace(go.Scatter(x=[0, mid], y=[share * 100, 100], mode="lines", name="projected",
                             line=dict(color=PALETTE["gold"], width=3)))
    fig.add_vrect(x0=lo, x1=hi, fillcolor=PALETTE["bad"], opacity=.2, line_width=0)
    fig.add_hline(y=100, line=dict(color=PALETTE["bad"], dash="dash"))
    fig.update_layout(template=TEMPLATE, height=210, xaxis_title=f"{t('seconds', lang)} from now",
                      yaxis=dict(title=f"{f.get('resource', '')} % of limit", range=[0, 110]), showlegend=False)
    return fig, True


def timeline(inc: dict | None, lang="en"):
    if not inc:
        return html.Div(t("no_incident", lang), className="muted")
    t0 = inc["opened_t"]
    return [html.Div([html.Span(f"+{e['t'] - t0:5.1f}{t('seconds', lang)}", className="tl-time"), html.Span(e["msg"])],
                     className="tl-item") for e in inc.get("timeline", [])]


def evidence(inc: dict | None, lang="en"):
    if not inc or not inc.get("evidence"):
        return html.Div(t("no_evidence", lang), className="muted")
    return [html.Div([html.B(e["id"]), html.Span(e["summary"])], className="ev") for e in inc["evidence"]]


def pill(text, cls):
    return html.Span(text, className=f"pill {cls}")


def report(inc: dict | None, lang="en"):
    if not inc or not inc.get("report"):
        return html.Div(t("no_incident", lang), className="muted")
    r = inc["report"]
    st = inc["status"]
    cls = "ok" if st == "recovered" else ("bad" if st in ("unresolved", "escalated", "partially_recovered") else "info")
    pills = [pill(inc["kind"], "info" if inc["kind"] == "reactive" else "warn"), pill(st, cls)]
    if inc.get("abstained"):
        pills.append(pill(t("abstained", lang), "warn"))
    conf = inc.get("confidence")
    kids = [html.Div(pills), html.P(r["summary"], style={"marginTop": "10px"}),
            html.Div([html.Span(f"{t('cause', lang)}: ", className="muted"), html.B(r["likely_cause"].replace("_", " ")),
                      html.Span(f"  ({conf:.0%} calibrated)" if conf is not None else "", className="muted")]),
            html.Div([html.Span(f"{t('runbook', lang)}: ", className="muted"), html.B(r.get("runbook_id") or "-")])]
    meta = inc.get("report_meta") or {}
    kids.append(html.Div(f"{t('provider', lang)}: {meta.get('provider', '?')}"
                         + (" (LLM disagreed; engine diagnosis kept)" if meta.get("llm_disagreed") else ""),
                         className="muted", style={"marginTop": "6px"}))
    if r.get("missing_information"):
        kids.append(html.Div("Missing: " + "; ".join(r["missing_information"]), className="muted"))
    return kids


def proof(inc: dict | None, lang="en"):
    if not inc or not inc.get("verification"):
        return html.Div(t("no_incident", lang), className="muted"), ""
    v, b = inc["verification"], inc.get("before") or {}
    a = inc.get("after") or {}

    def cell(key, before, after, fmt):
        return html.Div([html.Div(t(key, lang), className="k"),
                         html.Div([html.Span(fmt(before) if before is not None else "-", style={"color": PALETTE["bad"]}),
                                   html.Span(" → ", className="muted"),
                                   html.Span(fmt(after) if after is not None else "-", style={"color": PALETTE["ok"]})],
                                  className="v")], className="metric")
    pct = lambda x: f"{x:.0%}"
    ms = lambda x: f"{x * 1000:.0f} ms"
    ok = v["outcome"] == "recovered"
    banner = html.Div(t("recovered_banner" if ok else "not_recovered_banner", lang), className=f"banner {'ok' if ok else 'bad'}")
    grid = html.Div([cell("checkout_ok", b.get("checkout_success", 0.0), v["success_rate"], pct),
                     cell("error_ratio", b.get("error_ratio"), a.get("error_ratio"), pct),
                     cell("latency_ratio", b.get("p95_s"), a.get("p95_s"), ms)],
                    style={"display": "grid", "gridTemplateColumns": "repeat(3,1fr)"})
    return [banner, grid, html.Div(f"{v['probes']} synthetic checkouts held over the observation window; "
                                   f"max latency {v['p_max_latency_s']}s", className="muted")], ("ok" if ok else "bad")


def approvals(items: list, lang="en"):
    if not items:
        return html.Div(t("no_approvals", lang), className="muted")
    out = []
    for a in items:
        out.append(html.Div([
            html.Div([pill(a["risk"] + " risk", "warn"), html.B(f"{a['runbook_id']} → {a['service']}")]),
            html.Div(a["reason"], className="muted"),
            html.Div((a.get("report") or {}).get("summary", ""), style={"margin": "6px 0"}),
            html.Div([html.Button(t("approve", lang), id={"type": "approve", "id": a["incident_id"]},
                                  className="btn btn-gold btn-sm", n_clicks=0, style={"marginRight": "8px"}),
                      html.Button(t("reject", lang), id={"type": "reject", "id": a["incident_id"]},
                                  className="btn btn-outline-light btn-sm", n_clicks=0)])], className="ev"))
    return out


def scorecard(sc: dict | None):
    rows = (sc or {}).get("by_scenario") or {}
    if not rows:
        return html.Div("No scored runs yet.", className="muted")
    head = html.Tr([html.Th(h) for h in ("scenario", "runs", "detected", "top-1", "recovered", "false alerts",
                                         "harmful", "detect s", "verified s", "failed %")])
    def m(x):
        return "-" if not x else f"{x['mean']}±{x['sd']}"
    body = [html.Tr([html.Td(s), html.Td(r["runs"]), html.Td(r["detected"]), html.Td(r["top1"]), html.Td(r["recovered"]),
                     html.Td(r["false_alerts"]), html.Td(r["harmful_interventions"]), html.Td(m(r["time_to_detect_s"])),
                     html.Td(m(r["time_to_verified_recovery_s"])), html.Td(m(r["failed_request_pct"]))])
            for s, r in rows.items()]
    return html.Table([html.Thead(head), html.Tbody(body)], className="table table-sm table-dark",
                      style={"fontSize": ".8rem"})


def reveal_card(rev: dict | None, lang="en"):
    if not rev:
        return None
    tr, sc = rev["truth"], rev["score"]
    ok = sc.get("recovered") or sc.get("abstained_correctly")
    return html.Div([
        html.Div([html.Span(f"{t('reveal_truth', lang)}: ", className="muted"), html.B(tr["scenario"].replace("_", " "))]),
        html.Div([html.Span(f"{t('reveal_target', lang)}: ", className="muted"), html.B(tr["target"])]),
        html.Div(f"EternalAI → top-1 service correct: {sc.get('diagnosis_top1')}, cause correct: {sc.get('cause_correct')}, "
                 f"recovered: {sc.get('recovered')}, detect {sc.get('time_to_detect_s')}s, "
                 f"verified recovery {sc.get('time_to_verified_recovery_s')}s, failed requests {sc.get('failed_request_pct')}%, "
                 f"harmful interventions {sc.get('harmful_interventions')}, false alerts {sc.get('false_alerts')}",
                 style={"margin": "6px 0"}),
        html.Div(pill("matched" if ok else "check details", "ok" if ok else "warn"))], className="ev")
