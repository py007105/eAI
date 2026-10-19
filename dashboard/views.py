"""Pure rendering functions: backend JSON in, Plotly figures / Dash components out. No network here."""
from __future__ import annotations

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


def pill(text, cls):
    return html.Span(text, className=f"pill {cls}")


def muted(text):
    return html.Div(text, className="muted")


def blank_fig(message: str, height: int) -> go.Figure:
    """Empty chart with a message instead of meaningless 0..4 axes."""
    fig = go.Figure()
    fig.add_annotation(text=message, showarrow=False, font=dict(color=PALETTE["muted"], size=13))
    fig.update_layout(template=TEMPLATE, height=height, xaxis=dict(visible=False), yaxis=dict(visible=False),
                      margin=dict(l=10, r=10, t=10, b=10))
    return fig


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
            bad = states[a] not in ("healthy", "unknown") and states[b] not in ("healthy", "unknown")
            (x0, y0), (x1, y1) = POS[a], POS[b]
            fig.add_trace(go.Scatter(x=[x0, x1], y=[y0, y1], mode="lines", hoverinfo="skip", showlegend=False,
                                     line=dict(color=PALETTE["bad"] if bad else PALETTE["line"], width=5 if bad else 2,
                                               dash="solid" if bad else "dot")))
    xs, ys = zip(*(POS[s] for s in topology))
    colors = [col[states[s]] for s in topology]
    fig.add_trace(go.Scatter(x=xs, y=ys, mode="markers", hoverinfo="skip", showlegend=False,
                             marker=dict(size=86, color=colors, opacity=.16)))  # soft glow behind the nodes
    fig.add_trace(go.Scatter(
        x=xs, y=ys, mode="markers+text", text=list(topology), textposition="bottom center", showlegend=False,
        textfont=dict(size=14, color=PALETTE["text"]),
        marker=dict(size=48, color=colors, line=dict(color="#ffffff", width=1), opacity=.97),
        customdata=[[t(states[s], lang)] for s in topology],
        hovertemplate="%{text}: %{customdata[0]}<extra></extra>"))
    fig.update_layout(template=TEMPLATE, height=330, xaxis=dict(visible=False, range=[-.4, 2.4]),
                      yaxis=dict(visible=False, range=[-.15, 1.1]), margin=dict(l=10, r=10, t=10, b=10))
    return fig


def causes_fig(inc: dict | None, lang="en"):
    if not inc or not inc.get("ranking"):
        return blank_fig(t("no_causes", lang), 200)
    r = inc["ranking"][:4]
    fig = go.Figure(go.Bar(x=[x["score"] for x in r][::-1], y=[x["service"] for x in r][::-1], orientation="h",
                           marker=dict(color=[PALETTE["gold"] if i == 0 else PALETTE["violet"] for i in range(len(r))][::-1])))
    fig.update_layout(template=TEMPLATE, height=230,
                      xaxis=dict(range=[0, 1], automargin=True, title=dict(text=t("axis_support", lang), standoff=12)),
                      yaxis=dict(automargin=True), margin=dict(l=10, r=10, t=10, b=44))
    return fig


def margin_text(inc: dict | None, lang="en") -> str:
    if not inc or len(inc.get("ranking", [])) < 2:
        return ""
    r = inc["ranking"]
    return f"{t('uncertainty', lang)}: {r[0]['score'] - r[1]['score']:.2f}"


def forecast_fig(inc: dict | None, lang="en"):
    f = (inc or {}).get("forecasts") or []
    if not f:
        return blank_fig(t("no_forecast", lang), 230), False
    f = f[-1]
    share = f["share_of_limit_now"]
    lo, mid, hi = f["eta_earliest_s"], f["eta_s"], f["eta_latest_s"]  # straight projection from now to the limit
    fig = go.Figure(go.Scatter(x=[0, mid], y=[share * 100, 100], mode="lines", line=dict(color=PALETTE["gold"], width=3)))
    fig.add_vrect(x0=lo, x1=hi, fillcolor=PALETTE["bad"], opacity=.22, line_width=0)
    fig.add_hline(y=100, line=dict(color=PALETTE["bad"], dash="dash"))
    fig.update_layout(template=TEMPLATE, height=230, showlegend=False,
                      xaxis=dict(title=dict(text=f"{t('seconds', lang)} {t('axis_from_now', lang)}", standoff=10), automargin=True),
                      yaxis=dict(title=dict(text=f"{f.get('resource', '')} {t('axis_pct_limit', lang)}", standoff=10),
                                 range=[0, 112], automargin=True))
    return fig, True


def timeline(inc: dict | None, lang="en"):
    if not inc:
        return muted(t("no_incident", lang))
    t0 = inc["opened_t"]
    return [html.Div([html.Span(f"+{e['t'] - t0:5.1f}{t('seconds', lang)}", className="tl-time"), html.Span(e["msg"])],
                     className="tl-item") for e in inc.get("timeline", [])]


def evidence(inc: dict | None, lang="en"):
    if not inc or not inc.get("evidence"):
        return muted(t("no_evidence", lang))
    return [html.Div([html.B(e["id"]), html.Span(e["summary"])], className="ev") for e in inc["evidence"]]


def prob_text(inc: dict, conf, show_prob: bool, lang="en") -> str:
    """The percentage is the classifier's calibrated probability for ITS top class. When the system abstained, the label shown is 'insufficient evidence', which that
    probability does not describe (a novel window can still have a near-certain top class), so no percentage is shown for an abstained incident."""
    if conf is None:
        return ""
    if inc.get("abstained"):
        return f"  ({t('abstained_no_prob', lang)})"
    return f"  ({conf:.0%} {t('calibrated', lang)})" if show_prob else f"  ({t('prob_hidden', lang)})"


def report(inc: dict | None, lang="en", show_prob: bool = False):
    """`show_prob` is True only when the backend says the classifier's calibration check passed."""
    if not inc or not inc.get("report"):
        return muted(t("no_incident", lang))
    r, st = inc["report"], inc["status"]
    cls = "ok" if st == "recovered" else ("bad" if st in ("unresolved", "escalated", "partially_recovered") else "info")
    pills = [pill(t(f"kind_{inc['kind']}", lang), "info" if inc["kind"] == "reactive" else "warn"), pill(st, cls)]
    if inc.get("abstained"):
        pills.append(pill(t("abstained", lang), "warn"))
    conf = inc.get("confidence")
    meta = inc.get("report_meta") or {}
    kids = [html.Div(pills), html.P(r["summary"], style={"marginTop": "10px"}),
            html.Div([html.Span(f"{t('cause', lang)}: ", className="muted"), html.B(r["likely_cause"].replace("_", " ")),
                      html.Span(prob_text(inc, conf, show_prob, lang), className="muted")]),
            html.Div([html.Span(f"{t('runbook', lang)}: ", className="muted"), html.B(r.get("runbook_id") or "-")]),
            html.Div(f"{t('provider', lang)}: {meta.get('provider', '?')}"
                     + (f" ({t('llm_disagreed', lang)})" if meta.get("llm_disagreed") else ""),
                     className="muted", style={"marginTop": "6px"})]
    if r.get("missing_information"):
        kids.append(muted(f"{t('missing', lang)}: " + "; ".join(r["missing_information"])))
    return kids


def recovery_check(inc: dict | None, lang="en"):
    """Returns (children, glow class). An incident without a verification is never shown as recovered."""
    if not inc:
        return muted(t("no_incident", lang)), ""
    if not inc.get("verification"):
        return muted(t("not_verified", lang)), ""
    v, b, a = inc["verification"], inc.get("before") or {}, inc.get("after") or {}

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
    return [banner, grid, muted(f"{v['probes']} {t('check_footer', lang)} {v['p_max_latency_s']}{t('seconds', lang)}")], \
        ("ok" if ok else "bad")


RECENT_S = 300   # a closed incident colours the status line for 5 minutes, then the line returns to "healthy"


def status_line(incidents: list, approvals_: list, now: float, lang="en"):
    """One plain-language line from existing API fields only (/incidents, /approvals): (state, text).
    States, checked in this order: waiting, open, recovered or escalated (closed within RECENT_S), healthy."""
    if approvals_:
        a = approvals_[0]
        return "waiting", t("status_waiting", lang).format(what=f"{a['runbook_id']} → {a['service']}")
    active = [i for i in incidents if i["status"] in ("open", "executing", "verifying")]
    if active:
        i = active[-1]
        return "open", t("status_open", lang).format(svc=", ".join(i.get("services") or []) or "?", phase=t(f"phase_{i['status']}", lang))
    last = incidents[-1] if incidents else None
    if last and last.get("closed_t") and now - last["closed_t"] < RECENT_S:
        svc = ", ".join(last.get("services") or []) or "?"
        if last["status"] == "recovered":
            return "recovered", t("status_recovered", lang).format(svc=svc)
        if last["status"] in ("escalated", "unresolved", "partially_recovered"):
            return "escalated", t("status_escalated", lang).format(svc=svc, cause=(last.get("likely_cause") or "?").replace("_", " "))
    return "healthy", t("status_healthy", lang)


STATUS_CLS = {"waiting": "warn", "open": "bad", "escalated": "bad", "recovered": "ok", "healthy": "ok"}


def status_view(state: str, text: str):
    return html.Div(text, id="status_line", className=f"status-line {STATUS_CLS[state]}")


def approvals(items: list, lang="en"):
    if not items:
        return muted(t("no_approvals", lang))
    out = []
    for a in items:
        out.append(html.Div([
            html.Div([pill(f"{a['risk']} {t('risk', lang)}", "warn"), html.B(f"{a['runbook_id']} → {a['service']}")]),
            muted(a["reason"]),
            html.Div((a.get("report") or {}).get("summary", ""), style={"margin": "6px 0"}),
            html.Div([html.Button(t("approve", lang), id={"type": "approve", "id": a["incident_id"]},
                                  className="btn btn-gold btn-sm", n_clicks=0, style={"marginRight": "8px"}),
                      html.Button(t("reject", lang), id={"type": "reject", "id": a["incident_id"]},
                                  className="btn btn-ghost btn-sm", n_clicks=0)])], className="ev"))
    return out


def scorecard(sc: dict | None, lang="en"):
    rows = (sc or {}).get("by_scenario") or {}
    if not rows:
        return muted(t("no_scores", lang))
    heads = ("tbl_scenario", "tbl_runs", "tbl_detected", "tbl_top1", "tbl_recovered", "tbl_false", "tbl_harmful",
             "tbl_detect_s", "tbl_verified_s", "tbl_failed")
    m = lambda x: "-" if not x else f"{x['mean']}±{x['sd']}"
    body = [html.Tr([html.Td(s), html.Td(r["runs"]), html.Td(r["detected"]), html.Td(r["top1"]), html.Td(r["recovered"]),
                     html.Td(r["false_alerts"]), html.Td(r["harmful_interventions"]), html.Td(m(r["time_to_detect_s"])),
                     html.Td(m(r["time_to_verified_recovery_s"])), html.Td(m(r["failed_request_pct"]))])
            for s, r in rows.items()]
    return html.Table([html.Thead(html.Tr([html.Th(t(h, lang)) for h in heads])), html.Tbody(body)],
                      className="table table-sm table-dark", style={"fontSize": ".8rem"})


def reveal_card(rev: dict | None, lang="en"):
    if not rev:
        return None
    tr, sc = rev["truth"], rev["score"]
    ok = sc.get("recovered") or sc.get("abstained_correctly")
    s = t("seconds", lang)
    line = (f"{t('reveal_service', lang)}: {sc.get('diagnosis_top1')} · {t('reveal_cause', lang)}: {sc.get('cause_correct')} · "
            f"{t('reveal_recovered', lang)}: {sc.get('recovered')} · {t('reveal_detect', lang)} {sc.get('time_to_detect_s')}{s} · "
            f"{t('reveal_verified', lang)} {sc.get('time_to_verified_recovery_s')}{s} · "
            f"{t('reveal_failed', lang)} {sc.get('failed_request_pct')}% · {t('reveal_harmful', lang)} "
            f"{sc.get('harmful_interventions')} · {t('reveal_false', lang)} {sc.get('false_alerts')}")
    return html.Div([
        html.Div([html.Span(f"{t('reveal_truth', lang)}: ", className="muted"), html.B(tr["scenario"].replace("_", " "))]),
        html.Div([html.Span(f"{t('reveal_target', lang)}: ", className="muted"), html.B(tr["target"])]),
        html.Div(line, style={"margin": "6px 0"}),
        html.Div(pill(t("matched" if ok else "check_details", lang), "ok" if ok else "warn"))], className="ev")
