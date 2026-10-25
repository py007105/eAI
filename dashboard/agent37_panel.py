"""Agent37 panel for the operator dashboard: infrastructure twin, investigation trigger and result, incident graph.
Everything shown comes from the backend (/agent37/*, /incidents). Only the Investigate button spends Agent37 credit,
and it needs the approval token like every other write action."""
from __future__ import annotations

import math
import time

import plotly.graph_objects as go
from dash import Input, Output, State, dcc, html, no_update

HEALTH_CLS = {"healthy": "ok", "anomalous": "warn", "down": "bad", "unknown": "muted"}
EDGE_STYLE = {"DEPENDS_ON": ("#5b6b7a", "solid"), "AFFECTED_BY": ("#f2b84b", "solid"),
              "SUSPECTED_CAUSE": ("#ef6b6b", "dot"), "PROPOSED_ACTION": ("#72d7e5", "dash"),
              "EXECUTED_ACTION": ("#39ff14", "solid"), "VERIFIED_OUTCOME": ("#12b76a", "solid")}
NODE_COLOR = {"service": "#72d7e5", "incident": "#f2b84b", "fault": "#ef6b6b", "action": "#39ff14",
              "recommendation": "#b48cff", "outcome": "#12b76a"}


def layout_row(card):
    import dash_bootstrap_components as dbc
    return dbc.Row([
        dbc.Col(card([html.H4("Infrastructure twin", className="panel-h"),
                      html.Div("Live from EternalAI telemetry and incidents; no LLM call.", className="muted"),
                      html.Div(id="a37_twin", style={"marginTop": "8px"})]), lg=4),
        dbc.Col(card([html.H4("Agent37 incident investigator", className="panel-h"),
                      html.Div("Agent37 reads the incident and read-only tools and recommends. EternalAI's policy engine "
                               "decides; approval and execution use the existing controls. Each run spends Agent37 credit "
                               "and needs the approval token.", className="muted"),
                      html.Div([dcc.Dropdown(id="a37_incident", placeholder="Select an incident", className="dark-dd",
                                             style={"minWidth": "260px"}),
                                html.Button("Investigate with Agent37", id="a37_go", className="btn btn-gold", n_clicks=0),
                                html.Button("Re-run", id="a37_force", className="btn btn-ghost", n_clicks=0)],
                               style={"display": "flex", "gap": "8px", "margin": "10px 0", "flexWrap": "wrap"}),
                      html.Div(id="a37_msg", className="muted"), html.Div(id="a37_status", className="muted"),
                      html.Div(id="a37_result", style={"maxHeight": "460px", "overflowY": "auto", "marginTop": "8px"})],
                     cls="glow-cyan"), lg=8),
        dbc.Col(card([html.H4("Incident knowledge graph", className="panel-h"),
                      html.Div("Causes are suspected (classifier or Agent37), never confirmed; outcomes come from "
                               "checkout probes. Click a node for details.", className="muted"),
                      dcc.Dropdown(id="a37_graph_filter", placeholder="All services", className="dark-dd",
                                   style={"width": "200px", "marginTop": "6px"}),
                      dcc.Graph(id="a37_graph", config={"displayModeBar": False}, style={"height": "460px"}),
                      html.Div(id="a37_node", className="muted")]), lg=12),
    ])


def _twin_view(t: dict | None):
    if not t:
        return html.Div("Backend not reachable.", className="muted")
    rows = []
    for s, v in t["services"].items():
        last = v.get("last_agent37_investigation")
        rows.append(html.Tr([html.Td(s), html.Td(html.Span(v["health"], className=f"pill {HEALTH_CLS.get(v['health'], '')}")),
                             html.Td("-" if v.get("score") is None else f"{v['score']:.3f}"),
                             html.Td(", ".join(v.get("calls") or []) or "-"),
                             html.Td(", ".join(v.get("active_incidents") or []) or "-"),
                             html.Td(f"{last['fault']} ({last['confidence']})" if last else "-")]))
    return html.Table([html.Thead(html.Tr([html.Th(h) for h in ("service", "health", "score", "calls", "open incident",
                                                                "last Agent37 finding")])), html.Tbody(rows)],
                      className="table table-sm", style={"fontSize": "13px"})


def _fmt_t(x):
    return time.strftime("%I:%M:%S %p", time.localtime(x)).lstrip("0") if x else "-"


def _result_view(rec: dict | None):
    if not rec:
        return html.Div("No Agent37 investigation for this incident yet.", className="muted")
    out = [html.Div([html.B("Status: "), rec.get("status"), html.Span(f"  ({rec.get('error')})" if rec.get("error") else "",
                                                                      className="muted")])]
    f = rec.get("finding")
    if f:
        out += [html.Div([html.B("Suspected root cause: "), f"{f['fault']} on {f['root_cause_service']} "
                          f"(confidence {f['confidence']}, Agent37's assessment)"]),
                html.P(f["explanation"], style={"margin": "6px 0"}),
                html.Div([html.B("Evidence cited: "), ", ".join(f["evidence_ids"]) or "none"]),
                html.Div([html.B("Missing evidence: "), "; ".join(f["missing_evidence"]) or "none stated"]),
                html.Div([html.B("Suggested runbook: "), f["suggested_runbook"], "  ", html.Span(f.get("expected_impact", ""), className="muted")])]
        if (rec.get("validation") or {}).get("unknown_evidence_ids"):
            out.append(html.Div("Dropped evidence ids the incident does not have: "
                                + ", ".join(rec["validation"]["unknown_evidence_ids"]), className="muted"))
    p = rec.get("policy")
    if p:
        out.append(html.Div([html.B("EternalAI policy verdict on the suggestion: "), f"{p['verdict']}",
                             html.Span(f" - {p.get('reason', '')}", className="muted")], style={"marginTop": "6px"}))
    eng = rec.get("engine_pipeline")
    if eng:
        acts = "; ".join(f"{a['runbook_id']} on {a['service']}: {a['verdict']}"
                         f"{' executed' if a.get('executed') else ''}{' by ' + a['approved_by'] if a.get('approved_by') else ''}"
                         for a in eng["actions"]) or "no action"
        ver = (eng.get("verification") or {}).get("outcome") or "not verified yet"
        out.append(html.Div([html.B("EternalAI pipeline (authoritative): "), f"status {eng['status']}; {acts}; verification: {ver}. ",
                             html.Span("Approve or reject in the Approvals panel above.", className="muted")],
                            style={"marginTop": "6px"}))
    steps = rec.get("steps") or []
    if steps:
        items = []
        for s in steps:
            if s["kind"] == "tool":
                items.append(html.Li(f"{_fmt_t(s['t'])}  tool {s['tool']} {s.get('args') or ''}"))
            else:
                cost = s.get("cost_usd")
                items.append(html.Li(f"{_fmt_t(s['t'])}  Agent37 turn {s.get('response_id') or ''}: "
                                     f"{s.get('input_tokens')} in / {s.get('output_tokens')} out tokens"
                                     f"{'' if cost is None else f', reported cost {cost} USD'}"))
        out.append(html.Details([html.Summary(f"Execution trace ({len(steps)} steps)"), html.Ul(items)], style={"marginTop": "6px"}))
    return html.Div(out)


def _graph_fig(g: dict | None, service: str | None):
    fig = go.Figure()
    fig.update_layout(margin=dict(l=10, r=10, t=10, b=10), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      xaxis=dict(visible=False), yaxis=dict(visible=False), showlegend=True, height=440,
                      legend=dict(font=dict(size=11), orientation="h"))
    if not g:
        return fig
    nodes, edges = {n["id"]: n for n in g["nodes"]}, g["edges"]
    if service:
        keep_inc = {e["from"] for e in edges if e["type"] == "AFFECTED_BY" and e["to"] == f"svc:{service}"}
        keep = {f"svc:{service}"} | keep_inc | {e["to"] for e in edges if e["from"] in keep_inc}
        nodes = {k: v for k, v in nodes.items() if k in keep}
        edges = [e for e in edges if e["from"] in nodes and e["to"] in nodes]
    svc = [n for n in nodes if n.startswith("svc:")]
    other = [n for n in nodes if not n.startswith("svc:")]
    pos = {n: (math.cos(2 * math.pi * i / max(1, len(svc))), math.sin(2 * math.pi * i / max(1, len(svc)))) for i, n in enumerate(svc)}
    pos.update({n: (2.4 * math.cos(2 * math.pi * i / max(1, len(other)) + 0.3), 2.4 * math.sin(2 * math.pi * i / max(1, len(other)) + 0.3))
                for i, n in enumerate(other)})
    for typ, (color, dash) in EDGE_STYLE.items():
        xs, ys = [], []
        for e in edges:
            if e["type"] == typ and e["from"] != e["to"] and e["from"] in pos and e["to"] in pos:
                xs += [pos[e["from"]][0], pos[e["to"]][0], None]
                ys += [pos[e["from"]][1], pos[e["to"]][1], None]
        if xs:
            fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", line=dict(color=color, width=1.5, dash=dash), name=typ, hoverinfo="skip"))
    for kind, color in NODE_COLOR.items():
        ids = [n for n in nodes if nodes[n]["kind"] == kind]
        if ids:
            fig.add_trace(go.Scatter(x=[pos[n][0] for n in ids], y=[pos[n][1] for n in ids], mode="markers+text",
                                     marker=dict(size=16 if kind == "service" else 11, color=color),
                                     text=[nodes[n]["label"] for n in ids], textposition="bottom center",
                                     textfont=dict(size=10), customdata=ids, name=kind, hovertext=ids, hoverinfo="text"))
    return fig


def register(app, fetch, post):
    @app.callback(Output("a37_incident", "options"), Output("a37_graph_filter", "options"), Input("tick", "n_intervals"))
    def a37_options(_n):
        try:
            incs = fetch("/incidents")
        except Exception:  # noqa: BLE001 - backend down: keep the last options
            return no_update, no_update
        opts = [{"label": f"{i['id']} · {', '.join(i.get('services') or [])} · {i.get('likely_cause')} · {i['status']}",
                 "value": i["id"]} for i in reversed(incs)]
        svc = [{"label": s, "value": s} for s in ("web", "orders", "inventory", "payments")]
        return opts, svc

    @app.callback(Output("a37_msg", "children"), Input("a37_go", "n_clicks"), Input("a37_force", "n_clicks"),
                  State("a37_incident", "value"), State("token", "value"), prevent_initial_call=True)
    def a37_start(go_n, force_n, iid, token):
        from dash import ctx
        if not iid:
            return "Select an incident first."
        force = ctx.triggered_id == "a37_force"
        code, body = post(f"/agent37/investigate/{iid}?force={'true' if force else 'false'}", token, timeout=30)
        if code == 200:
            return f"Investigation {body.get('status')} for {iid}."
        return f"Not started (HTTP {code}): {body.get('detail', '')}"

    @app.callback(Output("a37_twin", "children"), Output("a37_result", "children"), Output("a37_status", "children"),
                  Output("a37_graph", "figure"), Input("tick", "n_intervals"), State("a37_incident", "value"),
                  State("a37_graph_filter", "value"))
    def a37_refresh(n, iid, svc):
        if n and n % 2:      # every other tick (3 s): plain backend reads, never an Agent37 call
            return no_update, no_update, no_update, no_update
        try:
            tw, g, st = fetch("/agent37/twin"), fetch("/agent37/graph"), fetch("/agent37/investigations")
        except Exception:  # noqa: BLE001
            return _twin_view(None), no_update, "Backend not reachable.", no_update
        rec = None
        if iid:
            try:
                rec = fetch(f"/agent37/investigations/{iid}")
            except Exception:  # noqa: BLE001 - 404: not investigated yet
                rec = None
        done = sum(1 for r in st if r.get("status") == "completed")
        return _twin_view(tw), _result_view(rec), f"{len(st)} investigations stored, {done} completed.", _graph_fig(g, svc)

    @app.callback(Output("a37_node", "children"), Input("a37_graph", "clickData"), prevent_initial_call=True)
    def a37_node(click):
        if not click or not click.get("points"):
            return no_update
        nid = click["points"][0].get("customdata")
        try:
            g = fetch("/agent37/graph")
        except Exception:  # noqa: BLE001
            return "Backend not reachable."
        rel = [e for e in g["edges"] if nid in (e["from"], e["to"])]
        return html.Ul([html.Li(f"{e['from']} -{e['type']}-> {e['to']}  [{e.get('source', '')}]"
                                + (f" verdict {e['verdict']}" if e.get("verdict") else "")
                                + (f" policy {e['policy_verdict']}" if e.get("policy_verdict") else "")) for e in rel]
                       or [html.Li(f"{nid}: no relations")])
