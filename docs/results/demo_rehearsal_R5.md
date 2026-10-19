# Demo rehearsal R5 (presenter, real browser, Ask first; rendered by `scripts/render_r5.py`)

R5 is a rehearsal, not a benchmark run: it enters no evaluated count and is kept apart from the frozen v2 statistics. The scorecard was not reset after R4, so it holds R4 and R5 together (9 runs); R5 runs are identified by run id. Every R5 run is listed. **R5 is partial:** a manual Reject and a timed five-minute sequence were not done and are left for a later R5b.

## Runs

| # | run | scenario / target (revealed) | injected | incident | s inject to incident | proposal | pending (brain timeline) | outcome | s inject to verified recovery | failed-request % | presenter's report |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1813a0c878 | disk_fill / orders | 00:25:44 | 28d9f6ec (disk_fill) | 8.5 | clear_temp_path → orders | 00:26:00 to 00:28:02 (121.2 s) | expired_unapproved; **visibility unresolved, observer not watching** | - | 25.55 | proposal expired; presenter was not watching |
| 2 | aad57af45f | crash / inventory | 00:34:35 | f7164d96 (down) | 4.1 | restart_service → inventory | 00:34:49 to 00:36:50 (120.8 s) | expired_unapproved; **visibility unresolved, observer not watching** | - | 100.0 | proposal expired; presenter was not watching |
| 3 | 9118ad85c9 | traffic_surge / web | 00:51:44 | none | - | none | - | no incident | - | 0.0 | 0 incidents |
| 4 | 2cdc9b587b | disk_fill / inventory | 01:02:22 | 263a2b59 (disk_fill) | 7.0 | clear_temp_path → inventory | 01:02:37 to 01:02:57 (20.2 s) | executed, approved_by dashboard | 58.4 | 21.79 | saw the card and clicked Approve |
| 5 | 81448e49df | cpu_burn / payments | 01:04:56 | 267ce994 (insufficient_evidence) | 7.9 | none | - | abstained | - | 0.0 | abstained, 0 actions |

## Brain offer vs dashboard view, per pending window (from the approval captures)

Capture folders: `20261020-005047` 00:51:00 to 00:53:39 (160 lines); `20261020-005344` 00:53:57 to 00:56:19 (143 lines); `20261020-005913` 00:59:25 to 01:00:17 (53 lines); `20261020-010131` 01:01:44 to 01:05:46 (243 lines).

The capture reads the brain's `GET /approvals` and a headless page on the dashboard once a second. The headless page goes through the same dashboard server as the presenter's browser, so it shows what the dashboard served; it does not prove what the presenter's own window displayed.

| run | pending window | seconds captured | brain listed this proposal (s) | dashboard showed an Approve button (s) | first brain listing | first dashboard card | seconds brain listed it but dashboard did not | brain GET errors | messages under the queue on the headless page (it never clicks, so the presenter's click messages are not captured) | screenshots |
|---|---|---|---|---|---|---|---|---|---|---|
| 1813a0c878 | 00:26:00 to 00:28:02 | 0 (no capture running) | - | - | - | - | - | - | - | - |
| aad57af45f | 00:34:49 to 00:36:50 | 0 (no capture running) | - | - | - | - | - | - | - | - |
| 2cdc9b587b | 01:02:37 to 01:02:57 | 20 | 20 | 20 | 01:02:38 | 01:02:38 | 0 | 0 | - | `20261020-010131/010242_pending.png`, `20261020-010131/010247_pending.png`, `20261020-010131/010252_pending.png`, `20261020-010131/010257_pending.png` |

Runs without a proposal, during capture:

- 9118ad85c9 (traffic_surge): 60 captured seconds between injection and the end of scoring; brain listed a proposal in 0, dashboard showed an Approve button in 0.
- 81448e49df (cpu_burn): 24 captured seconds between injection and the end of scoring; brain listed a proposal in 0, dashboard showed an Approve button in 0.

Approval audit entries during R5 (brain `/audit`):

- 01:02:57: clear_temp_path on inventory by human:dashboard, ok=True

## Notes

- The two expiries (1813a0c878, aad57af45f) ran before the capture tool existed. They are recorded as **visibility unresolved, observer not watching**: the presenter was not watching the dashboard and cannot say what the watcher window showed. They are not classified as a dashboard defect or as operator error.
- The watcher one-liner given for R5 always printed PENDING on Windows PowerShell 5.1: `@(Invoke-RestMethod …)` wraps an empty JSON array into a one-element array, so `.Count` was never 0. Corrected form (prints PENDING only when a proposal is pending): `while ($true) { $a = @((Invoke-RestMethod http://localhost:8000/approvals) | Where-Object { $_ }); if ($a.Count) { "$(Get-Date -f HH:mm:ss) PENDING"; $a | Select-Object incident_id, service, runbook_id | Format-Table } else { "$(Get-Date -f HH:mm:ss) none pending" }; Start-Sleep 2 }`. `scripts/approval_capture.py` replaces it for evidence.
- Still open for R5b: Reject clicked by hand, and the five-minute sequence timed end to end.
