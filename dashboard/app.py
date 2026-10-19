"""EternalAI dashboard (Dash + Plotly). Talks only to the EternalAI backend over REST.

    python dashboard/app.py          # http://localhost:8050 ; BACKEND_URL defaults to http://localhost:8000

A background thread polls the backend and caches the latest state. Callbacks only read the cache, so they
return instantly even when the backend is slow or down (a callback slower than the 1.5 s refresh interval
would otherwise have every response discarded by Dash and the page would freeze).
"""
import os
import sys
import threading
import time
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
TOPOLOGY_FALLBACK = {"web": ["orders", "inventory"], "orders": ["inventory", "payments"], "inventory": [], "payments": []}
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.CYBORG], title="EternalAI", suppress_callback_exceptions=True)


def fetch(path, timeout=(1.0, 3.0)):
    r = requests.get(f"{BACKEND}{path}", timeout=timeout)
    r.raise_for_status()
    return r.json()


class Poller:
    """Polls the backend about once a second; `get` returns None when the cached value is stale or missing."""
    PATHS = {"status": "/status", "services": "/services", "incidents": "/incidents", "approvals": "/approvals",
             "scorecard": "/scorecard"}
    MAX_AGE_S = 6.0

    def __init__(self):
        self.cache, self.run_id, self._started = {}, None, False
        self.lock = threading.Lock()

    def start_once(self):
        with self.lock:
            if self._started:
                return
            self._started = True
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):
        while True:
            t0 = time.time()
            paths = dict(self.PATHS)
            if self.run_id:
                paths["challenge"] = f"/challenge/{self.run_id}/status"
            for key, path in paths.items():
                try:
                    val = fetch(path)
                    with self.lock:
                        self.cache[key] = (val, time.time())
                except (requests.RequestException, ValueError):
                    with self.lock:
                        self.cache.pop(key, None)
                    if key == "status":
                        break  # backend is down; do not wait on every other endpoint
            time.sleep(max(0.0, 1.0 - (time.time() - t0)))

    def get(self, key, default=None):
        with self.lock:
            v = self.cache.get(key)
        return v[0] if v and time.time() - v[1] < self.MAX_AGE_S else default


poller = Poller()


def post(path, token=None, json=None, timeout=20):
    token = token.strip() if token else token       # a pasted token often carries a trailing newline or space
    try:
        r = requests.post(f"{BACKEND}{path}", json=json or {}, timeout=timeout,
                          headers={"X-Approval-Token": token} if token else {})
        return r.status_code, (r.json() if r.content else {})
    except (requests.exceptions.InvalidHeader, UnicodeEncodeError):
        # requests' own message repeats the header value, i.e. the token; never show or log that
        return 0, {"detail": t("token_invalid", "en")}
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
                                         clearable=False, className="dark-dd", style={"width": "120px"}),
                            dcc.Dropdown(id="mode", options=[{"label": t(f"mode_{m}"), "value": m}
                                                             for m in ("watch-only", "ask-first", "autopilot")],
                                         clearable=False, placeholder=t("mode"), className="dark-dd", style={"width": "160px"}),
                            dbc.Input(id="token", type="password", placeholder=t("token_placeholder"),
                                      style={"width": "170px"})],
                           style={"display": "flex", "gap": "10px", "alignItems": "center"})], className="hero"),
        html.Div(id="statusbar", style={"marginBottom": "10px", "minHeight": "26px"}),
        html.Div(id="mode_msg", className="muted"),
        dbc.Row([
            dbc.Col(card([html.Div(id="t_map"), dcc.Graph(id="map", config={"displayModeBar": False})]), lg=7),
            dbc.Col([card([html.Div(id="t_report"), html.Div(id="report")], id="report_card"),
                     card([html.Div(id="t_causes"), dcc.Graph(id="causes", config={"displayModeBar": False}),
                           html.Div(id="margin", className="muted"), html.Div(id="confnote", className="muted")])], lg=5)]),
        dbc.Row([
            dbc.Col(card([html.Div(id="t_timeline"), html.Div(id="timeline")]), lg=4),
            dbc.Col(card([html.Div(id="t_evidence"), html.Div(id="evidence", style={"maxHeight": "300px", "overflowY": "auto"})]), lg=4),
            dbc.Col(card([html.Div(id="t_forecast"), dcc.Graph(id="forecast", config={"displayModeBar": False}),
                          html.Div(id="forecast_note", className="muted"),
                          html.Div(t("forecast_caveat"), id="forecast_caveat", className="muted", style={"fontStyle": "italic", "marginTop": "4px"})]), lg=4)]),
        dbc.Row([
            dbc.Col(card([html.Div(id="t_approvals"), html.Div(id="approvals"), html.Div(id="approval_msg", className="muted")]), lg=5),
            dbc.Col(card([html.Div(id="t_check"), html.Div(id="check")], id="check_card"), lg=7)]),
        dbc.Row([
            dbc.Col(card([html.Div(id="t_challenge"),
                          html.Div(id="challenge_text", className="muted"),
                          html.Div([html.Button(id="start", className="btn btn-gold", n_clicks=0, style={"marginRight": "10px"}),
                                    html.Button(id="reveal", className="btn btn-ghost", n_clicks=0)],
                                   style={"margin": "10px 0"}),
                          html.Div(id="reveal_out")], cls="glow-cyan"), lg=5),
            dbc.Col(card([html.Div(id="t_score"), html.Div(id="scorecard", style={"overflowX": "auto"})]), lg=7)]),
        dcc.Store(id="run_id"), dcc.Store(id="revealed"),
        dcc.Interval(id="tick", interval=1500, n_intervals=0)])


app.layout = layout


@app.callback(
    Output("t_map", "children"), Output("t_report", "children"), Output("t_causes", "children"),
    Output("t_timeline", "children"), Output("t_evidence", "children"), Output("t_forecast", "children"),
    Output("t_approvals", "children"), Output("t_check", "children"), Output("t_challenge", "children"),
    Output("t_score", "children"), Output("start", "children"), Output("reveal", "children"), Output("tagline", "children"),
    Output("confnote", "children"), Input("lang", "value"))
def titles(lang):
    P = views.panel_title
    return (P("mdi:graph-outline", "panel_map", lang, "ok"), P("mdi:file-document-outline", "panel_report", lang),
            P("mdi:target-variant", "panel_causes", lang), P("mdi:timeline-clock-outline", "panel_timeline", lang),
            P("mdi:magnify", "panel_evidence", lang), P("mdi:chart-line", "panel_forecast", lang),
            P("mdi:shield-check-outline", "panel_approvals", lang), P("mdi:check-decagram-outline", "panel_check", lang, "ok"),
            P("mdi:sword-cross", "panel_challenge", lang), P("mdi:podium-gold", "panel_scorecard", lang),
            t("challenge_start", lang), t("challenge_reveal", lang), t("app_tagline", lang), t("confidence_note", lang))


@app.callback(
    Output("statusbar", "children"), Output("map", "figure"), Output("causes", "figure"), Output("margin", "children"),
    Output("report", "children"), Output("timeline", "children"), Output("evidence", "children"),
    Output("forecast", "figure"), Output("forecast_note", "children"), Output("approvals", "children"),
    Output("check", "children"), Output("check_card", "className"), Output("report_card", "className"),
    Output("scorecard", "children"),
    Input("tick", "n_intervals"), Input("lang", "value"))
def refresh(_, lang):
    poller.start_once()
    status = poller.get("status")
    if status is None:
        return (html.Span(t("backend_offline", lang), style={"color": "#ff4d6d"}),
                views.service_map({}, TOPOLOGY_FALLBACK, lang), views.causes_fig(None, lang), "",
                views.report(None, lang), views.timeline(None, lang), views.evidence(None, lang),
                views.forecast_fig(None, lang)[0], "", views.approvals([], lang), views.recovery_check(None, lang)[0],
                "panel", "panel", views.scorecard(None, lang))
    svc = poller.get("services") or {"services": {}, "topology": TOPOLOGY_FALLBACK}
    incs = poller.get("incidents") or []
    inc = incs[-1] if incs else None
    fig_f, _ = views.forecast_fig(inc, lang)
    f = (inc or {}).get("forecasts") or []
    note = (f"{t('eta', lang)}: {f[-1]['eta_earliest_s']:.0f}-{f[-1]['eta_latest_s']:.0f}{t('seconds', lang)}" if f else "")
    p, pcls = views.recovery_check(inc, lang)
    fallback = status.get("fallbacks_in_use") or []
    bar = [views.pill(status["mode"], "info"),
           views.pill(t("models_ok", lang) if not fallback else f"{t('models_fallback', lang)}: {', '.join(fallback)}",
                      "ok" if not fallback else "warn")]
    if status["breakers_open"]:
        bar.append(views.pill(f"{t('breakers_open', lang)}: {', '.join(status['breakers_open'])}", "bad"))
    rcls = "panel glow-bad" if inc and inc["status"] in ("open", "awaiting_approval", "executing", "verifying") else (
        "panel glow-ok" if inc and inc["status"] == "recovered" else "panel")
    return (bar, views.service_map(svc["services"], svc["topology"] or TOPOLOGY_FALLBACK, lang), views.causes_fig(inc, lang),
            views.margin_text(inc, lang),
            views.report(inc, lang, bool((status.get("calibration") or {}).get("show_probability"))),
            views.timeline(inc, lang), views.evidence(inc, lang),
            fig_f, note, views.approvals(poller.get("approvals") or [], lang), p,
            f"panel glow-{pcls}" if pcls else "panel", rcls, views.scorecard(poller.get("scorecard"), lang))


@app.callback(Output("approval_msg", "children"),
              Input({"type": "approve", "id": ALL}, "n_clicks"), Input({"type": "reject", "id": ALL}, "n_clicks"),
              State("token", "value"), State("lang", "value"), prevent_initial_call=True)
def decide(_a, _r, token, lang):
    ctx = callback_context
    if not ctx.triggered or not ctx.triggered[0]["value"]:
        return dash.no_update
    trig = ctx.triggered_id
    code, body = post(f"/approvals/{trig['id']}/{trig['type']}", token, {"approver": "dashboard"})
    return t("action_done", lang) if code == 200 else f"{t('action_refused', lang)} ({code}): {body.get('detail', '')}"


@app.callback(Output("mode_msg", "children"), Input("mode", "value"), State("token", "value"), State("lang", "value"),
              prevent_initial_call=True)
def set_mode(mode, token, lang):
    code, body = post("/mode", token, {"mode": mode})
    return "" if code == 200 else f"{t('mode_failed', lang)} ({code}): {body.get('detail', '')}"


@app.callback(Output("run_id", "data"), Output("challenge_text", "children"), Output("revealed", "data"),
              Output("reveal_out", "children"),
              Input("start", "n_clicks"), Input("reveal", "n_clicks"), Input("tick", "n_intervals"),
              State("run_id", "data"), State("lang", "value"), State("revealed", "data"), prevent_initial_call=False)
def challenge(start, reveal, _tick, run_id, lang, revealed):
    trig = callback_context.triggered_id
    if trig == "start" and start:
        code, body = post("/challenge/start")
        if code == 200:
            poller.run_id = body["run_id"]
            return body["run_id"], t("challenge_wait", lang), None, None
        return run_id, f"{t('challenge_fail', lang)} ({code}): {body.get('detail', '')}", None, None
    if not run_id:
        return None, t("challenge_idle", lang), None, None
    poller.run_id = run_id
    if trig == "reveal" and reveal:
        code, body = post_get(f"/challenge/{run_id}/reveal")
        if code == 200:
            return run_id, "", body, views.reveal_card(body, lang)
        return run_id, t("challenge_early", lang), revealed, None
    if revealed:
        return run_id, "", revealed, views.reveal_card(revealed, lang)
    st = poller.get("challenge") or {}
    msg = (f"{t('challenge_wait', lang)} ({st.get('elapsed_s', 0):.0f}{t('seconds', lang)})" if st.get("state") == "running"
           else t("challenge_done", lang) if st.get("state") == "finished" else str(st.get("state", "")))
    return run_id, msg, None, None


def post_get(path, timeout=10):
    try:
        r = requests.get(f"{BACKEND}{path}", timeout=timeout)
        return r.status_code, (r.json() if r.content else {})
    except requests.RequestException as e:
        return 0, {"detail": str(e)}


if __name__ == "__main__":
    poller.start_once()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8050")), debug=False)
