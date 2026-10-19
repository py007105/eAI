# Incidents opened while no challenge was running (before R4; script output)

Read at 2026-10-19 20:38:32 IST from the brain's `/incidents`; the evaluator's scorecard held 0 runs, so no challenge had been started since the launcher's scorecard reset. These are incidents the brain opened on the idle stack (load generator running, no fault injected by the evaluator). Their cause is **unverified**: they are not fault detections, and they enter no evaluated count. They were left in place (no brain restart, no history deletion).

| incident | opened (IST) | services flagged | likely cause | abstained | status | actions proposed or executed |
|---|---|---|---|---|---|---|
| 8cb358b0 | 2026-10-19 18:14:34 | payments | insufficient_evidence | True | escalated | 0 |
| 9f015e00 | 2026-10-19 18:55:18 | payments | insufficient_evidence | True | escalated | 0 |
| cda8a0c1 | 2026-10-19 20:17:08 | inventory, orders, web | insufficient_evidence | True | escalated | 0 |

Total: 3 incidents, 0 actions.

**Telling them apart from a challenge during R4.** The dashboard's report, timeline and evidence panels show the most recent incident; they do not show its id or clock time, and the timeline is relative (+0.8 s ...). Until a challenge opens a new incident, the panels show the last idle incident above. To check by id and opening time (read-only), in window B: `(Invoke-RestMethod http://localhost:8000/incidents) | Select-Object id, @{n='opened';e={[DateTimeOffset]::FromUnixTimeSeconds([int64]$_.opened_t).LocalDateTime}}, status, likely_cause`. An incident opened before you ran `demo_challenge.py start` is not from that challenge. The evaluator's own count, printed by `demo_challenge.py reveal <RUN_ID>` (`incidents_opened`), includes only incidents opened from one second before that run's injection onward; an idle incident can still open during a challenge, and the evaluator counts it if it falls in that window.
