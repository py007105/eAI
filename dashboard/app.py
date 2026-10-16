"""EternalAI dashboard (Dash + Plotly). Talks only to the EternalAI backend over REST.

    python dashboard/app.py          # http://localhost:8050 ; BACKEND_URL defaults to http://localhost:8000
"""
import os
import sys
from pathlib import Path

import dash
import dash_bootstrap_components as dbc
import requests
from dash import ALL, Input, Output, State, callback_context, dcc, html

sys.path.insert(0, str(Path(__file__).parent))
import views  # noqa: E402
from labels import t  # noqa: E402
from theme import TEMPLATE  # noqa: E402, F401  (registers the Plotly template)

BACKEND = os.getenv("BACKEND_URL", "http://localhost:8000")
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.CYBORG], title="EternalAI",
                suppress_callback_exceptions=True)


def get(path, default=None, timeout=3):
    try:
        r = requests.get(f"{BACKEND}{path}", timeout=timeout)
        return r.json() if r.ok else default
    except requests.RequestException:
        return default


def post(path, token=None, json=None, timeout=20):
    try:
        r = requests.post(f"{BACKEND}{path}", json=json or {}, timeout=timeout,
                          headers={"X-Approval-Token": token} if token else {})
        return r.status_code, (r.json() if r.content else {})
    except requests.RequestException as e:
        return 0, {"detail": str(e)}


def card(children, cls="", id=None):
    extra = {"id": id} if id else {}
    return html.Div(children, className=f"panel {cls}", **extra)


def layout():
    return dbc.Container(fluid=True, children=[
        html.Div([html.Div([html.H1([t("app_title"), " ", html.Span(t("brahmastra"), className="deva")]),
                            html.Div(t("app_tagline"), className="tag", id="tagline")]),
                  html.Div([dcc.Dropdown(id="lang", options=[{"label": "English", "value": "en"},
                                                              {"label": "हिन्दी", "value": "hi"}], value="en",
                                         clearable=False, style={"width": "110px", "color": "#000"}),
                            dcc.Dropdown(id="mode", options=[{"label": t(f"mode_{m}"), "value": m}
                                                             for m in ("watch-only", "ask-first", "autopilot")],
                                         clearable=False, placeholder=t("mode"), style={"width": "150px", "color": "#000"}),
                            dbc.Input(id="token", type="password", placeholder=t("token_placeholder"),
                                      style={"width": "170px"})],
                           style={"display": "flex", "gap": "10px", "alignItems": "center"})], className="hero"),
        html.Div(id="statusbar", className="muted", style={"marginBottom": "10px"}),
        html.Div(id="mode_msg", className="muted"),
        dbc.Row([
            dbc.Col(card([html.Div(id="t_map"), dcc.Graph(id="map", config={"displayModeBar": False})]), lg=7),
            dbc.Col([card([html.Div(id="t_report"), html.Div(id="report")], id="report_card"),
                     card([html.Div(id="t_causes"), dcc.Graph(id="causes", config={"displayModeBar": False}),
                           html.Div(id="margin", className="muted"),
                           html.Div(t("confidence_note"), className="muted", id="confnote")])], lg=5)]),
        dbc.Row([
            dbc.Col(card([html.Div(id="t_timeline"), html.Div(id="timeline")]), lg=4),
            dbc.Col(card([html.Div(id="t_evidence"), html.Div(id="evidence", style={"maxHeight": "300px", "overflowY": "auto"})]), lg=4),
            dbc.Col(card([html.Div(id="t_forecast"), dcc.Graph(id="forecast", config={"displayModeBar": False}),
                          html.Div(id="forecast_note", className="muted")]), lg=4)]),
        dbc.Row([
            dbc.Col(card([html.Div(id="t_approvals"), html.Div(id="approvals"), html.Div(id="approval_msg", className="muted")]), lg=5),
            dbc.Col(card([html.Div(id="t_proof"), html.Div(id="proof")], id="proof_card"), lg=7)]),
        dbc.Row([
            dbc.Col(card([html.Div(id="t_challenge"),
                          html.Div(id="challenge_text", className="muted"),
                          html.Div([html.Button(id="start", className="btn btn-gold", n_clicks=0, style={"marginRight": "10px"}),
                                    html.Button(id="reveal", className="btn btn-outline-light", n_clicks=0)],
                                   style={"margin": "10px 0"}),
                          html.Div(id="reveal_out")], cls="glow-cyan"), lg=5),
            dbc.Col(card([html.Div(id="t_score"), html.Div(id="scorecard", style={"overflowX": "auto"})]), lg=7)]),
        dcc.Store(id="run_id"), dcc.Store(id="revealed"),
        dcc.Interval(id="tick", interval=1500, n_intervals=0)])


app.layout = layout


@app.callback(
    Output("t_map", "children"), Output("t_report", "children"), Output("t_causes", "children"),
    Output("t_timeline", "children"), Output("t_evidence", "children"), Output("t_forecast", "children"),
    Output("t_approvals", "children"), Output("t_proof", "children"), Output("t_challenge", "children"),
    Output("t_score", "children"), Output("start", "children"), Output("reveal", "children"), Output("tagline", "children"),
    Input("lang", "value"))
def titles(lang):
    P = views.panel_title
    return (P("mdi:graph-outline", "panel_map", lang, "ok"), P("mdi:file-document-outline", "panel_report", lang),
            P("mdi:target-variant", "panel_causes", lang), P("mdi:timeline-clock-outline", "panel_timeline", lang),
            P("mdi:magnify", "panel_evidence", lang), P("mdi:chart-line", "panel_forecast", lang),
            P("mdi:shield-check-outline", "panel_approvals", lang), P("mdi:check-decagram-outline", "panel_proof", lang, "ok"),
            P("mdi:sword-cross", "panel_challenge", lang), P("mdi:podium-gold", "panel_score", lang),
            t("challenge_start", lang), t("challenge_reveal", lang), t("app_tagline", lang))


@app.callback(
    Output("statusbar", "children"), Output("map", "figure"), Output("causes", "figure"), Output("margin", "children"),
    Output("report", "children"), Output("timeline", "children"), Output("evidence", "children"),
    Output("forecast", "figure"), Output("forecast_note", "children"), Output("approvals", "children"),
    Output("proof", "children"), Output("proof_card", "className"), Output("report_card", "className"),
    Output("scorecard", "children"),
    Input("tick", "n_intervals"), Input("lang", "value"))
def refresh(_, lang):
    status = get("/status")
    if status is None:
        empty = views.service_map({}, {"web": ["orders", "inventory"], "orders": ["inventory", "payments"],
                                       "inventory": [], "payments": []}, lang)
        return (html.Span(t("backend_offline", lang), style={"color": "#ff4d6d"}), empty, views.causes_fig(None),
                "", views.report(None, lang), views.timeline(None, lang), views.evidence(None, lang),
                views.forecast_fig(None)[0], "", views.approvals([], lang), views.proof(None, lang)[0],
                "panel", "panel", views.scorecard(None))
    svc = get("/services", {"services": {}, "topology": {}})
    incs = get("/incidents", []) or []
    inc = incs[-1] if incs else None
    fig_f, has_f = views.forecast_fig(inc, lang)
    f = (inc or {}).get("forecasts") or []
    note = (f"{t('eta', lang)}: {f[-1]['eta_earliest_s']:.0f}-{f[-1]['eta_latest_s']:.0f}{t('seconds', lang)}"
            if f else t("no_forecast", lang))
    p, pcls = views.proof(inc, lang)
    fallback = status.get("fallbacks_in_use") or []
    bar = [views.pill(status["mode"], "info"),
           views.pill(t("models_ok", lang) if not fallback else f"{t('models_fallback', lang)}: {', '.join(fallback)}",
                      "ok" if not fallback else "warn"),
           views.pill(f"breakers open: {', '.join(status['breakers_open'])}", "bad") if status["breakers_open"] else ""]
    rcls = "panel glow-bad" if inc and inc["status"] in ("open", "awaiting_approval", "executing", "verifying") else (
        "panel glow-ok" if inc and inc["status"] == "recovered" else "panel")
    return (bar, views.service_map(svc["services"], svc["topology"] or {"web": []}, lang), views.causes_fig(inc, lang),
            views.margin_text(inc, lang), views.report(inc, lang), views.timeline(inc, lang), views.evidence(inc, lang),
            fig_f, note, views.approvals(get("/approvals", []) or [], lang), p, f"panel glow-{pcls}" if pcls else "panel",
            rcls, views.scorecard(get("/scorecard")))


@app.callback(Output("approval_msg", "children"),
              Input({"type": "approve", "id": ALL}, "n_clicks"), Input({"type": "reject", "id": ALL}, "n_clicks"),
              State("token", "value"), prevent_initial_call=True)
def decide(_a, _r, token):
    ctx = callback_context
    if not ctx.triggered or not ctx.triggered[0]["value"]:
        return dash.no_update
    trig = ctx.triggered_id
    code, body = post(f"/approvals/{trig['id']}/{trig['type']}", token, {"approver": "dashboard"})
    return "Done." if code == 200 else f"Refused ({code}): {body.get('detail', '')}"


@app.callback(Output("mode_msg", "children"), Input("mode", "value"), State("token", "value"), prevent_initial_call=True)
def set_mode(mode, token):
    code, body = post("/mode", token, {"mode": mode})
    return "" if code == 200 else f"Mode not changed ({code}): {body.get('detail', '')}"


@app.callback(Output("run_id", "data"), Output("challenge_text", "children"), Output("revealed", "data"),
              Output("reveal_out", "children"),
              Input("start", "n_clicks"), Input("reveal", "n_clicks"), Input("tick", "n_intervals"),
              State("run_id", "data"), State("lang", "value"), State("revealed", "data"), prevent_initial_call=False)
def challenge(start, reveal, _tick, run_id, lang, revealed):
    trig = callback_context.triggered_id
    if trig == "start" and start:
        code, body = post("/challenge/start")
        if code == 200:
            return body["run_id"], t("challenge_wait", lang), None, None
        return run_id, f"Could not start ({code}): {body.get('detail', '')}", None, None
    if not run_id:
        return None, t("challenge_idle", lang), None, None
    if trig == "reveal" and reveal:
        r = get(f"/challenge/{run_id}/reveal", timeout=10)
        if r:
            return run_id, "", r, views.reveal_card(r, lang)
        return run_id, "Not finished yet: the truth is revealed only after scoring.", revealed, None
    st = get(f"/challenge/{run_id}/status") or {}
    if revealed:
        return run_id, "", revealed, views.reveal_card(revealed, lang)
    msg = (t("challenge_wait", lang) + f" ({st.get('elapsed_s', 0):.0f}s)" if st.get("state") == "running"
           else "Run finished. You can reveal the truth." if st.get("state") == "finished" else str(st.get("state", "")))
    return run_id, msg, None, None


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8050")), debug=False)
