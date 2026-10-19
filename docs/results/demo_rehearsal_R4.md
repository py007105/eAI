# Demo rehearsal R4 (presenter, real browser, Ask first; rendered by `scripts/render_r4.py`)

R4 is a rehearsal, not a benchmark run: it enters no evaluated count and is kept apart from the frozen v2 statistics. Every attempt the evaluator scored is listed (4 runs on the scorecard). **R4 ran after the assumed rehearsal cutoff (21:10 IST) and finished after the assumed freeze (23:10 IST).** Brain mode when the records were copied: ask-first.

| # | run | scenario / target (revealed) | injected (IST) | incident | s inject to incident | proposal (runbook → service) | proposal pending (IST) | outcome of proposal | s inject to verified recovery | failed-request % | evaluator: detected / recovered / abstained correctly / harmful | reported by presenter |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 8e7b5f1436 | traffic_surge / web | 23:20:55.2 | none | - | none | - | - | - | 0.0 | False / None / None / 0 | no (found on the scorecard) |
| 2 | fbc8f2f45f | disk_fill / payments | 23:24:08.7 | 165d4e40 (disk_fill) | 5.7 | clear_temp_path → payments | 23:24:22.1 to 23:26:23.2 | expired_unapproved | - | 25.68 | True / False / None / 0 | yes |
| 3 | 26d7614e46 | error_spike / orders | 23:33:00.4 | 478aa7aa (error_spike) | 8.2 | restart_service → orders | 23:33:16.1 to 23:34:21.5 | executed, approved_by dashboard | 104.3 | 9.54 | True / True / None / 0 | yes |
| 4 | 87745c4b3c | cpu_burn / inventory | 23:44:19.3 | fb080fb2 (insufficient_evidence) | 7.4 | none | - | abstained | - | 0.0 | True / False / True / 0 | yes |

Phase timings (s), from the brain's incident timeline and the evaluator's score; the evaluator's preparation wait before injection was not recorded for R4 and is not part of any of these:

| run | injection to incident | incident to proposal pending | proposal to approval (human delay) or expiry | approval to verified recovery | injection to verified recovery (evaluator) |
|---|---|---|---|---|---|
| 8e7b5f1436 | - | - | - | - | - |
| fbc8f2f45f | 5.7 | 7.6 | 121.2 (expired, no approval) | - | - |
| 26d7614e46 | 8.2 | 7.6 | 65.4 (approved) | 23.2 | 104.3 |
| 87745c4b3c | 7.4 | - | - | - | - |

Approval audit (brain `/audit`, the only entries in this brain process):

- 23:34:21.5: restart_service on orders by human:dashboard, ok=True, result {'restarted': 'orders'}

Incidents outside the four challenge windows (opened with no challenge's injection window covering them; cause unverified, not fault detections):

- 8cb358b0 18:14:34.3 on payments: insufficient_evidence, abstained True, escalated, 0 actions
- 9f015e00 18:55:18.6 on payments: insufficient_evidence, abstained True, escalated, 0 actions
- cda8a0c1 20:17:08.9 on inventory, orders, web: insufficient_evidence, abstained True, escalated, 0 actions
- 59482089 21:52:59.4 on orders, web: insufficient_evidence, abstained True, escalated, 0 actions
- 8ab243b4 23:22:06.4 on web: insufficient_evidence, abstained True, escalated, 0 actions
- ee70f314 23:26:32.4 on orders: insufficient_evidence, abstained True, escalated, 0 actions
- 15a152ae 23:35:04.6 on orders: insufficient_evidence, abstained True, escalated, 0 actions

7 incidents; cause unknown. No recovery actions executed for these incidents; their operational impact was not evaluated.

## Findings (partial validation, not a pass)

- **Demonstrated in R4:** detection and correct diagnosis on both supported faults; one dashboard approval executed and the brain's own synthetic checkout verified recovery; the presenter's approval token is verified by that authenticated approval (audit `human:dashboard, ok=True`; the approve endpoint refuses a missing or wrong token before acting); the unseen fault (cpu_burn) abstained with no proposal, established from the incident inside its injection window, one run, not a rate.
- **Unresolved:** run fbc8f2f45f's proposal was pending in the brain for about 121 s and expired unapproved while the presenter reported "Nothing waiting for approval" on the dashboard. The dashboard server answered every refresh in that window with HTTP 200 and logged no error, but what the browser displayed cannot be established (no recording). The cause is unresolved: neither confirmed operator error nor a confirmed dashboard defect. The later successful approval does not explain it.
- **Launch method of run 8e7b5f1436 is unconfirmed** (not reported by the presenter; found on the scorecard). It is kept in the table.
- **Not exercised manually:** the Reject button. R4's unseen run tested abstention, not Reject. Reject was exercised only by the automated R3b (`docs/results/demo_rehearsals.md`: disk_fill on orders, rejected_by_dashboard, escalated).
- **No screen recording** of R4 exists, so there is no fallback video.
- **Five minutes** is a presentation target, not a measured runtime; no rehearsal timed the sequence end to end.
- **Deadlines:** R4 ran after the assumed rehearsal cutoff (21:10 IST) and finished after the assumed freeze (23:10 IST); this report and the DEMO.md corrections were written after the freeze.
- The frozen v2 benchmark and its cpu_burn limitations (2 of 3 abstained in v2, 4 of 5 in v1, never pooled; seed 426 acted on the wrong service) are unchanged and are not affected by these rehearsal runs.
