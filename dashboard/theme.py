"""Palette and the custom Plotly template shared by every chart."""
import plotly.graph_objects as go
import plotly.io as pio

PALETTE = {
    "bg": "#07080f", "panel": "#0f1220", "panel2": "#151a2e", "line": "#262d4a", "text": "#e8ebf7",
    "muted": "#8a93b8", "gold": "#ffb21e", "saffron": "#ff6b2c", "cyan": "#2ee6d6", "violet": "#8b5cf6",
    "ok": "#2ee6a6", "warn": "#ffb21e", "bad": "#ff4d6d",
}

pio.templates["eternal"] = go.layout.Template(layout=go.Layout(
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Noto Sans Devanagari, Inter, Segoe UI, sans-serif", color=PALETTE["text"], size=12),
    colorway=[PALETTE["cyan"], PALETTE["gold"], PALETTE["violet"], PALETTE["saffron"], PALETTE["ok"]],
    xaxis=dict(gridcolor=PALETTE["line"], zerolinecolor=PALETTE["line"], linecolor=PALETTE["line"]),
    yaxis=dict(gridcolor=PALETTE["line"], zerolinecolor=PALETTE["line"], linecolor=PALETTE["line"]),
    margin=dict(l=30, r=20, t=30, b=30), hoverlabel=dict(bgcolor=PALETTE["panel2"], font_color=PALETTE["text"]),
))
pio.templates.default = "eternal"
TEMPLATE = "eternal"
