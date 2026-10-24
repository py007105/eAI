# Live check: dashboard chart, explanation and statistics cards

Commit: `e1e8d3e` (dashboard run from this checkout's source); started 2026-10-24 12:56:46 IST, finished 2026-10-24 12:57:34 IST.
Backend: `http://127.0.0.1:8000` (brain mode `autopilot`); read-only GET requests only. This is the real dashboard with live data, separate from the synthetic preview (`dashboard/preview/`).
Service shown: `web`; warm-up 30 s; page ready after 3.5 s; free RAM at start 1.77 GB.

| id | result | detail |
|---|---|---|
| D1 | PASS | 4 lines; points per line [46, 46, 46, 46] |
| D2 | PASS | page: ['Nothing to report for this service at this tick.']; API before: []; API after: [] |
| D3 | PASS | 2 incidents from /incidents; expected rows ['escalated\t1', 'recovered\t1', 'Incidents without an executed action\t1']; missing [] |
| D5 | PASS | Live: the last 5 minutes this page has polled from /services. / Live: incidents the running brain has recorded since it started (/incidents). |
| D4 | PASS | सेवा चार्ट / घटना आँकड़े; heading आंकड़े क्या कहते हैं |

**5 of 5 checks passed**

Screenshots: `docs/screenshots/charts_live_en.png`, `docs/screenshots/charts_live_hi.png` (the two cards only).
Not checked live: the behaviour with the backend down (unit-tested in `tests/test_dashboard_charts_live.py`).

Context (main session): the stack ran the candidate images built from `71eb2f5` (no rebuild; the brain code is the same in
this commit), started under the main session's own Docker lock 12:53:51-12:57:48 IST. One real crash on web was injected
through the evaluator before the check (detected, recovered, 1 action executed), so `/incidents` held real records. By
the end of the warm-up the crash had recovered, so D2 compared an empty explanation with an empty API answer: it confirms
the wiring, not the wording of a live fault sentence. A first attempt at 12:37-12:40 IST failed before any check (page
load over the 30 s limit); the limit was raised in `e1e8d3e`. Visible flaw: right-axis tick labels overlap the dashed
"normal" line.
