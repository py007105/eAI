# Hand-back: dashboard components (charts, stats, plain-language explanations)
- Branch: team/mihir-dashboard-charts
- Starting commit: 65dd9fe014e2bdfe6cede2cd9f69b0a014604f93    - Final commit: this commit (see `git log -1` / the PR head — adding this file is itself the last commit, so its own hash cannot be baked into its own text)

## Changed files
- `dashboard/charts_labels.py`: English/Hindi templates for explanations, chart legends, stats table, preview UI.
- `dashboard/explain_words.py`: `explain_service` — plain-language sentences from a service's features.
- `dashboard/charts.py`: `History`, `service_figure`, `incident_stats`, `stats_table`.
- `dashboard/preview/make_samples.py`: deterministic synthetic sample-data generator.
- `dashboard/preview/sample_services.json`, `sample_incidents.json`: generated synthetic data (labelled).
- `dashboard/preview/preview_app.py`: standalone Dash preview on 127.0.0.1:8071.
- `dashboard/preview/README.md`: how to run the preview.
- `tests/test_dashboard_explain.py`, `tests/test_dashboard_charts.py`: focused tests.
- `docs/DASHBOARD_CHARTS.md`: component documentation.

## Milestones
| # | status (done / partial / not done) | evidence |
|---|---|---|
| 1 sample data | done | `make_samples.py` writes both files; two runs are byte-identical (verified by hash); inventory `mem_share` at tick 59 = 0.7375, orders `lat_ratio` at tick 59 = 2.5, web `error_ratio` = 0.05 from tick 40 and `restarts_in_window` = 1 only at ticks 50-52, payments has no `"features"` key at ticks 10-12 — all spot-checked directly against the generated JSON |
| 2 explanations | done | 6/6 tests in `test_dashboard_explain.py` pass: exact sentence match for inventory/orders at tick 59 (English and Hindi), empty list for a normal service and for missing/NaN/infinite features, and confirmation that `score`/`*_z` values never appear in output |
| 3 charts and stats | done | 7/7 tests in `test_dashboard_charts.py` pass: `History(max_points=5)` keeps the last 5 of 8 ticks; payments' series is `None` exactly at ticks 10-12; `service_figure` for inventory has 4 traces and uses the `eternal` template; an unknown service and an empty `History` both return the blank figure; `incident_stats` on the sample incidents gives exactly n=2/median=9.0/range 6-12 (detect→action), n=2/median=25.5/range 23-28 (action→verified), `by_status` = {recovered: 2, escalated: 1, awaiting_approval: 1}, `not_executed` = 2; `incident_stats([])` gives `None`/`None`/`{}`/0 |
| 4 preview page | done, functionally | `preview_app.py` serves `http://127.0.0.1:8071` (confirmed: HTTP 200, `_dash-layout` contains the banner text, the chart, and the tick slider). The Dash `update()` callback was invoked directly in Python (bypassing the browser) for (lang=en/hi, service=inventory, tick=0/59): at tick 59 it returns 4 chart traces and an explanation containing "74%" and "38%" (English) or the matching Hindi sentence; at tick 0 it returns "Nothing to report...". I could **not** click through the page in an actual browser — the Claude-in-Chrome extension was not connected in this session — so this is verified at the data/callback level, not by eye. **Update (main session, 2026-10-24 00:34 IST):** the page was then driven in headless Chromium through its real controls (language dropdown, tick slider) for the three screenshots in milestone 5; the rendered explanation text matched the callback results above |
| 5 screenshots | done (by the main session, 2026-10-24 00:34 IST) | captured in headless Chromium (Playwright) from the running standalone preview, no Docker: `docs/screenshots/charts_preview_en.png` (inventory, tick 59, English), `charts_preview_hi.png` (same, Hindi), `charts_empty.png` (inventory, tick 0: "Nothing to report for this service at this tick."). The synthetic-data banner is visible in all three; images inspected by eye. Script: `dashboard/preview/capture_screenshots.py` |
| 6 docs | done | `docs/DASHBOARD_CHARTS.md` and this note now list the screenshots |

## Tests (exact last lines)
- `pytest tests\test_dashboard_explain.py tests\test_dashboard_charts.py tests\test_dashboard_views.py` -> `21 passed in 0.33s`

## Live evidence
- Not live verified. All results use synthetic sample data (`dashboard/preview/*.json`). Not connected to the live dashboard, the brain API, or any network service.

## Dependencies / configuration changes
- None (only the packages already in `dashboard/requirements.txt` + `pytest==9.1.1`, in my local `.venv`).

## Known limitations
- Milestone 5 was completed by the main session, not in Mihir's session (his session had no browser automation). The browser capture drove the real page controls (language dropdown, tick slider).
- Seen in the screenshots: on the Hindi page the banner ("SYNTHETIC SAMPLE DATA - not live") and the "Language" label stay in English, and the vertical Hindi y-axis title is cramped; the empty state still draws empty axes.
- `score` and `anomalous` are present in the sample data (per the schema in the assignment) but intentionally never read by `explain_words.py` — this is by design, to prove the raw score is never surfaced.
- `web`'s `anomalous` flag is left `False` throughout the sample data: the assignment's story table only specifies `anomalous: true` for `inventory` and `orders`; `web`'s deviation (rising error rate, a restart window) is still fully visible through its raw features and through `explain_service`, just not through the detector's own flag.

## Integration requests for Claude
| file | what is needed | proposed change | why |
|---|---|---|---|
| `dashboard/app.py` | feed `charts.History` from the Poller's `/services` data each tick | add a `History` per service, updated on each poll interval; a chart card using `charts.service_figure`; a stats card using `charts.incident_stats` + `charts.stats_table` fed from real incident records; callbacks for a service selector | connect these components to live data |
| `dashboard/labels.py` | (optional) fold `charts_labels.py` into the main label file once stable | if preferred for a single source of truth, merge `CHART_LABELS` into `LABELS` | reduce duplicate label files long-term (not required for this hand-back) |

## Submission
- PR: opened against `plan-complete` from `team/mihir-dashboard-charts` — see the message accompanying this hand-back for the link and final commit hash.

## Integration order and rollback
- Independent of the other teammates' branches.
- Rollback: Claude merges with `git merge --no-ff`; `git revert -m 1 <merge commit>` undoes it without rewriting history.
