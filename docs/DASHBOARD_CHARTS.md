# Dashboard charts, statistics, and plain-language explanations

Mihir's package (branch `team/mihir-dashboard-charts`): per-service charts, a stats panel, and
plain-language service explanations, plus a standalone preview using synthetic sample data.

**Verified on synthetic data only; not connected to the live dashboard.**

## Components

### `dashboard/explain_words.py`

`explain_service(name, features, lang="en") -> list[str]` turns one service's feature dict into
short sentences (English or Hindi), in a fixed order, skipping any condition whose feature is
missing, `None`, `NaN`, or infinite. It never includes `score` or any `*_z` value — those keys
are simply never read.

Display thresholds (constants at the top of the file; they decide what is *shown*, not what
counts as anomalous):

| constant | value | meaning |
|---|---|---|
| `SLOW_LAT_RATIO` | 1.5 | mention latency at or above 1.5x normal |
| `ERROR_SHARE` | 0.01 | mention errors at or above 1% of requests |
| `HIGH_MEM_SHARE` | 0.60 | mention memory at or above 60% of the limit |
| `RISING_MEM_SLOPE` | 0.01 | also say "rising" when growth is at least 1%/min |
| `HIGH_TRAFFIC_RATIO` | 2.0 | mention traffic at or above 2x normal |

Sentence templates (English and Hindi) live in `dashboard/charts_labels.py`, not in
`dashboard/labels.py`.

### `dashboard/charts.py`

- `History(max_points=300)`: `add(snapshot)` appends one tick and drops the oldest once past
  `max_points`; `series(service, feature)` returns `(ts, values)` with `None` for a missing or
  non-finite value (a gap in the chart, never a 0).
- `service_figure(history, service, lang="en")`: one line per feature that has at least one
  value in the visible history (`lat_ratio`, `rps_ratio` on the left "times normal" axis with a
  dashed line at 1.0; `error_ratio`, `mem_share` ×100 on the right "%" axis). X axis is seconds
  relative to the latest tick (0 = now, negative = "seconds ago"). Falls back to
  `views.blank_fig("No data yet", 260)` when the service has no data at all.
- `incident_stats(incidents)`: `detect_to_action` and `action_to_verified`
  (`{n, median, min, max}` or `None`), `by_status` (counts), `not_executed` (incidents with no
  executed action — not averaged into the timing stats).
- `stats_table(stats, lang="en")`: a small `dbc.Table` rendering of the above; `"-"` where a
  value is `None`.

### `dashboard/preview/`

- `make_samples.py`: writes `sample_services.json` (60 ticks, t = 0..118s, deterministic — two
  runs are byte-identical) and `sample_incidents.json` (4 incidents). Both start with a `"label"`
  field stating the data is synthetic.
  - `inventory`: normal through tick 19, then a memory leak from tick 20 (`mem_share` rises by
    0.0125 per tick, reaching 0.7375 at tick 59; `mem_slope_share_per_min` 0.375; `anomalous`
    true).
  - `orders`: normal until tick 30, then `lat_ratio` 2.5, `anomalous` true.
  - `web`: `error_ratio` 0.05 from tick 40; `restarts_in_window` 1 at ticks 50-52.
  - `payments`: normal throughout, but the whole `"features"` key is **absent** at ticks 10-12
    (to exercise the gap-handling in `History.series`).
- `preview_app.py`: a standalone Dash app on **http://127.0.0.1:8071** (no network calls, no
  threads, no background polling — it only reacts to the language / service / tick controls).
  Shows the synthetic-data banner, the chart, the explanation sentences, and the stats table.
- `README.md`: how to run it.

## Running the preview

```powershell
cd "$HOME\eAI-mihir"
.\.venv\Scripts\python.exe dashboard\preview\preview_app.py
```

Then open http://127.0.0.1:8071. Port 8071 was free on the machine this was built on; see
`dashboard/preview/README.md` if it is occupied on yours.

## Tests

`tests/test_dashboard_explain.py` and `tests/test_dashboard_charts.py` — see
`docs/handback/mihir.md` for the exact command and last line of output.

## Screenshots

`docs/screenshots/charts_preview_en.png`, `charts_preview_hi.png`, `charts_empty.png` — see
`docs/handback/mihir.md` for status; the Chrome browser-automation tool was not connected in this
session, so these could not be captured here. See the hand-back for what to do next.

**Verified on synthetic data only; not connected to the live dashboard.**
