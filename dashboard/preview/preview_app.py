"""Standalone preview of Mihir's dashboard-charts package, served on http://127.0.0.1:8071.

SYNTHETIC SAMPLE DATA ONLY: loads the hand-made files in this folder (see make_samples.py).
Not connected to the live dashboard, the brain API or any network service. No background
polling: the page only reacts to the language / service / tick controls.

Run with:  python dashboard\\preview\\preview_app.py
"""
import json
import sys
from pathlib import Path

PREVIEW_DIR = Path(__file__).resolve().parent
DASHBOARD_DIR = PREVIEW_DIR.parent
sys.path.insert(0, str(DASHBOARD_DIR))

import dash  # noqa: E402
import dash_bootstrap_components as dbc  # noqa: E402
from dash import Input, Output, dcc, html  # noqa: E402

from charts import History, incident_stats, service_figure, stats_table  # noqa: E402
from charts_labels import ct  # noqa: E402
from explain_words import explain_service  # noqa: E402
from theme import PALETTE  # noqa: E402

with open(PREVIEW_DIR / "sample_services.json", encoding="utf-8") as f:
    SERVICES_DATA = json.load(f)
with open(PREVIEW_DIR / "sample_incidents.json", encoding="utf-8") as f:
    INCIDENTS_DATA = json.load(f)

TICKS = SERVICES_DATA["ticks"]
SERVICE_NAMES = sorted({name for tick in TICKS for name in tick["services"]})
STATS = incident_stats(INCIDENTS_DATA["incidents"])

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.CYBORG])
app.title = "EternalAI dashboard charts preview"

app.layout = dbc.Container([
    html.Div(ct("banner", "en"), id="synthetic-banner", style={
        "backgroundColor": PALETTE["warn"], "color": "#1a1a1a", "padding": "10px 16px",
        "fontWeight": "bold", "textAlign": "center", "borderRadius": "6px", "marginTop": "12px",
    }),
    dbc.Row([
        dbc.Col([
            html.Label(ct("select_language", "en")),
            dcc.Dropdown(id="lang", clearable=False, value="en",
                        options=[{"label": "English", "value": "en"}, {"label": "हिन्दी", "value": "hi"}]),
        ], width=3),
        dbc.Col([
            html.Label(id="service-label"),
            dcc.Dropdown(id="service", clearable=False, value=SERVICE_NAMES[0],
                        options=[{"label": s, "value": s} for s in SERVICE_NAMES]),
        ], width=3),
        dbc.Col([
            html.Label(id="tick-label"),
            dcc.Slider(id="tick", min=0, max=len(TICKS) - 1, step=1, value=0,
                       marks={0: "0", len(TICKS) - 1: str(len(TICKS) - 1)}),
        ], width=6),
    ], className="my-3"),
    dcc.Graph(id="chart"),
    html.Div(id="explanation", className="my-3"),
    html.Hr(),
    html.Div(id="stats"),
], fluid=True, style={"maxWidth": "1000px"})


@app.callback(
    Output("chart", "figure"),
    Output("explanation", "children"),
    Output("stats", "children"),
    Output("service-label", "children"),
    Output("tick-label", "children"),
    Input("lang", "value"),
    Input("service", "value"),
    Input("tick", "value"),
)
def update(lang, service, tick_idx):
    lang = lang or "en"
    tick_idx = tick_idx or 0

    history = History(max_points=len(TICKS))
    for tick in TICKS[: tick_idx + 1]:
        history.add(tick)

    fig = service_figure(history, service, lang)

    latest = TICKS[tick_idx]["services"].get(service) or {}
    features = latest.get("features")
    sentences = explain_service(service, features, lang) if features is not None else []
    explanation = html.Div(
        [html.P(ct("explanation_title", lang), className="fw-bold")]
        + ([html.P(s) for s in sentences] if sentences else [html.P(ct("no_sentences", lang))])
    )

    stats_children = html.Div([html.P(ct("stat_by_status", lang), className="fw-bold"), stats_table(STATS, lang)])

    return (fig, explanation, stats_children,
           f"{ct('select_service', lang)}:", f"{ct('select_tick', lang)}: {tick_idx}")


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8071, debug=False)
