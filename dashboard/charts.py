"""Per-service history buffer, per-service chart, and incident statistics.

Pure rendering / data functions, same style as views.py: no network calls here.
"""
from __future__ import annotations

import math
import statistics

import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from dash import html

from charts_labels import ct
from theme import PALETTE, TEMPLATE
from views import blank_fig

LEFT_AXIS_FEATURES = ("lat_ratio", "rps_ratio")   # "times normal"
RIGHT_AXIS_FEATURES = ("error_ratio", "mem_share")  # "%", values times 100
CHART_FEATURES = LEFT_AXIS_FEATURES + RIGHT_AXIS_FEATURES


def _finite(v):
    if v is None:
        return None
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    if math.isnan(v) or math.isinf(v):
        return None
    return v


class History:
    """Keeps at most `max_points` ticks per service; the oldest are dropped first."""

    def __init__(self, max_points: int = 300):
        self.max_points = max_points
        self.ticks: list[tuple[float, dict]] = []  # [(t, services_dict), ...]

    def add(self, snapshot: dict) -> None:
        self.ticks.append((snapshot["t"], snapshot.get("services") or {}))
        if len(self.ticks) > self.max_points:
            self.ticks = self.ticks[-self.max_points:]

    def series(self, service: str, feature: str) -> tuple[list[float], list[float | None]]:
        ts, vals = [], []
        for t, services in self.ticks:
            ts.append(t)
            svc = services.get(service)
            vals.append(_finite((svc.get("features") or {}).get(feature)) if svc else None)
        return ts, vals


def service_figure(history: History, service: str, lang: str = "en") -> go.Figure:
    if not history.ticks:
        return blank_fig(ct("no_chart_data", lang), 260)
    latest = history.ticks[-1][0]

    traces = []
    for feature in CHART_FEATURES:
        ts, vals = history.series(service, feature)
        if all(v is None for v in vals):
            continue
        traces.append((feature, [t - latest for t in ts], vals))

    if not traces:
        return blank_fig(ct("no_chart_data", lang), 260)

    fig = go.Figure()
    for feature, xs, vals in traces:
        on_right = feature in RIGHT_AXIS_FEATURES
        ys = [None if v is None else (v * 100 if on_right else v) for v in vals]
        fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", connectgaps=False,
                                 name=ct(f"feat_{feature}", lang),
                                 yaxis="y2" if on_right else "y1"))
    fig.add_hline(y=1.0, line=dict(color=PALETTE["muted"], dash="dash"))
    fig.update_layout(
        template=TEMPLATE, height=260,
        # own margins + automargin: with the template's 20 px right margin the % tick labels overlapped each other
        margin=dict(l=60, r=60, t=20, b=40),
        xaxis=dict(title=dict(text=ct("axis_seconds_ago", lang))),
        yaxis=dict(title=dict(text=ct("axis_times_normal", lang), standoff=16), automargin=True, nticks=5),
        yaxis2=dict(title=dict(text=ct("axis_percent", lang), standoff=8), overlaying="y", side="right",
                    automargin=True, showgrid=False, tickformat=".0f", nticks=5, rangemode="tozero"),
        legend=dict(orientation="h"),
    )
    return fig


def incident_stats(incidents: list[dict]) -> dict:
    detect_vals, action_vals = [], []
    by_status: dict[str, int] = {}
    not_executed = 0

    for inc in incidents:
        status = inc.get("status")
        by_status[status] = by_status.get(status, 0) + 1

        executed = [a for a in inc.get("actions", []) if a.get("executed") and a.get("executed_t") is not None]
        if not executed:
            not_executed += 1
            continue

        first = executed[0]
        detect_vals.append(first["executed_t"] - inc["opened_t"])

        verification = inc.get("verification")
        if verification and verification.get("t") is not None:
            action_vals.append(verification["t"] - first["executed_t"])

    def summarize(values):
        if not values:
            return None
        return {"n": len(values), "median": statistics.median(values), "min": min(values), "max": max(values)}

    return {
        "detect_to_action": summarize(detect_vals),
        "action_to_verified": summarize(action_vals),
        "by_status": by_status,
        "not_executed": not_executed,
    }


def stats_table(stats: dict, lang: str = "en"):
    def row(label_key, summary):
        if summary is None:
            n, median, lo, hi = "-", "-", "-", "-"
        else:
            n = str(summary["n"])
            median = f"{summary['median']:.1f}"
            lo = f"{summary['min']:.1f}"
            hi = f"{summary['max']:.1f}"
        return html.Tr([html.Td(ct(label_key, lang)), html.Td(n), html.Td(median), html.Td(lo), html.Td(hi)])

    time_table = dbc.Table([
        html.Thead(html.Tr([html.Th(ct("stat_metric", lang)), html.Th(ct("stat_n", lang)),
                            html.Th(ct("stat_median", lang)), html.Th(ct("stat_min", lang)),
                            html.Th(ct("stat_max", lang))])),
        html.Tbody([
            row("stat_detect_to_action", stats.get("detect_to_action")),
            row("stat_action_to_verified", stats.get("action_to_verified")),
        ]),
    ], bordered=False, striped=True, size="sm")

    status_rows = [html.Tr([html.Td(status), html.Td(str(count))])
                  for status, count in sorted((stats.get("by_status") or {}).items())]
    status_rows.append(html.Tr([html.Td(ct("stat_not_executed", lang)), html.Td(str(stats.get("not_executed", 0)))]))
    status_table = dbc.Table([
        html.Thead(html.Tr([html.Th(ct("stat_by_status", lang)), html.Th("")])),
        html.Tbody(status_rows),
    ], bordered=False, striped=True, size="sm")

    return html.Div([time_table, status_table])
