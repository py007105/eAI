# Demo rehearsals (rendered by `scripts/render_rehearsals.py`; all three are reported)

Each rehearsal started from the launcher (`scripts/demo.ps1 -ConfirmReset`): export checksums verified first, scorecard volume reset through the launcher's confirm path, stack started under T3 with the dashboard on, inventory restocked, preflight passed. Rehearsals are not benchmark runs and enter no evaluated count.

## R1: LLM on (`gemini-3.5-flash-lite`), headless, scripted operator

Brain at start: {'brain': 'eternalai', 'mode': 'ask-first', 'fallbacks_in_use': []}. Total 522.9 s. Emulated dashboard polls: 973 requests, 0 errors (an emulation of the dashboard's REST polling, not the real dashboard).

| challenge | mode | scenario (revealed) | target | s to first incident | s to verified recovery | s from start to scorecard | min free RAM GB | Gemini requests | report provider(s) | executed | incidents | recovered | failed-request % | notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| supported fault, autopilot, fixed seed | autopilot | crash | payments | 5.8 | 44.2 | 106.3 | 1.9 | 1 | gemini | restart_service@payments | 1 | True | 10.22 | - |
| hidden supported/healthy draw, ask-first + scripted approver | ask-first | latency (hidden draw) | web | 14.2 | 58.2 | 118.9 | 1.9 | 1 | gemini | restart_service@web | 1 | True | 4.48 | - |
| UNSEEN fault cpu_burn, ask-first, proposal recorded and rejected | ask-first | cpu_burn | web | 9.7 | - | 83.2 | 1.9 | 1 | template | - | 1 | False | 93.22 | LLM fallback: gemini: ValueError |
| healthy surge, ask-first | ask-first | traffic_surge | web | - | - | 111.9 | 2.23 | 0 | - | - | 0 | - | 0.0 | - |

cpu_burn (unseen) record: {"diagnosis": [{"root": "web", "ranking": [{"service": "web", "score": 0.9847402137336985}, {"service": "payments", "score": 0.009433610859963247}, {"service": "orders", "score": 0.002913087703169036}, {"service": "inventory", "score": 0.002913087703169036}], "abstained": true, "novelty": 3.5748, "threshold": 1.116572955468316, "confidence": 0.9685779375527189, "status": "escalated"}], "proposals": [], "abstained_correctly": true, "actions_executed": 0}

## R2: keys removed (`-NoLlm`), headless: template fallback

Brain at start: {'brain': 'eternalai', 'mode': 'ask-first', 'fallbacks_in_use': []}. Total 435.9 s.

| challenge | mode | scenario (revealed) | target | s to first incident | s to verified recovery | s from start to scorecard | min free RAM GB | Gemini requests | report provider(s) | executed | incidents | recovered | failed-request % | notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| supported fault, autopilot, fixed seed (template fallback) | autopilot | crash | payments | 5.2 | 41.8 | 103.8 | 1.81 | 0 | template | restart_service@payments | 1 | True | 9.56 | - |
| hidden supported/healthy draw, autopilot | autopilot | disk_fill (hidden draw) | inventory | 7.9 | 39.6 | 140.6 | 1.55 | 0 | template, template | clear_temp_path@inventory, clear_temp_path@inventory | 2 | True | 0.0 | 2 incidents for one fault |
| healthy good_deploy, autopilot | autopilot | good_deploy | orders | - | - | 114.3 | 1.77 | 0 | - | - | 0 | - | 0.86 | - |

## R3: human-driven, real browser, dashboard open

Recorder: 440 samples over 1413 s; minimum free RAM with the browser open: **2.28 GB** (at the start 5.88 GB).

Reported by the presenter (R3, real browser): a token pasted from terminal text gave 'Mode not changed (0): Invalid leading whitespace, reserved character(s)...' (the message repeated the header value); in the unseen segment the amber nodes were web, orders and inventory, payments green; no approval card, only 'escalated: insufficient evidence'; the causes chart had inventory far ahead (margin 0.95); the report said 'written by gemini (LLM disagreed; engine diagnosis kept)'; 'Likely cause: insufficient evidence (100% calibrated)' was shown. A disk_fill run appeared that the presenter did not start by script.

| incident | opened (s after the R3 stack start) | statuses seen | cause | abstained | proposal seen (service, runbook) | ranking at the time | anomalous services when the proposal was pending | final |
|---|---|---|---|---|---|---|---|---|
| 69da5af3 | 363 | open > escalated | insufficient_evidence | True | - | web 0.25, orders 0.25, inventory 0.25 | - | escalated |
| aa853bb7 | 551 | open > awaiting_approval > escalated | disk_fill | False | payments, clear_temp_path | payments 0.98, web 0.01, inventory 0.01 | payments | escalated |
| fb8eac89 | 689 | open > escalated | insufficient_evidence | True | - | payments 0.98, orders 0.01, web 0.00 | - | escalated |
| d14615e6 | 763 | open > escalated | insufficient_evidence | True | - | inventory 0.96, payments 0.02, orders 0.01 | - | escalated |
| 76d98d30 | 816 | open > escalated | insufficient_evidence | True | - | payments 0.26, inventory 0.26, orders 0.24 | - | escalated |

Evaluator rows for the runs started during R3 (scorecard after the launcher's reset):

| scenario | target | detected | time to detect s | recovered | s to verified recovery | failed-request % | actions executed | abstained correctly |
|---|---|---|---|---|---|---|---|---|
| traffic_surge | web | False | - | - | - | 0.0 | 0 | - |
| disk_fill | payments | True | 7.2 | False | - | 27.19 | 0 | - |
| cpu_burn | inventory | True | 7.3 | False | - | 58.91 | 0 | True |

## R3b: automated in the real dashboard (headless Chromium, below-normal priority, throwaway token)

Started 2026-10-19T17:30:12; free RAM at start 3.07 GB.

Token handling (mode change from the dashboard):

- wrong token: `Mode not changed (403): invalid approval token`
- token with a non-Latin-1 character: `Mode not changed (0): Token contains invalid characters (spaces, line breaks or symbols). Clear the field and retype it by hand.`
- throwaway token, Ask first: `(no error)`; brain mode afterwards: ask-first

- draw without a proposal (approve path, draw 1): traffic_surge on web, incidents 0
- draw without a proposal (approve path, draw 2): traffic_surge on web, incidents 0
- draw without a proposal (approve path, draw 3): good_deploy on web, incidents 0
- draw without a proposal (approve path, draw 4): good_deploy on inventory, incidents 0

### Approve path (draw 5)

- card read from the page: `low riskrestart_service → orders | ask-first: low-risk action requires approval | orders shows signs of down (classifier confidence 1.00). Proposed runbook: restart_service. Recovery is only confirmed after the synthetic checkout passes. | ApproveReject`
- anomalous services when the card appeared: orders
- s from fault injection to card: at least 12.3; s from card to click: 0.6; message after click: `Done.`
- s from the challenge start to card: 213.1 (includes the evaluator's settle wait before injecting: 45 s, or 200 s after a release change)
- verification banner: `The service recovered, and EternalAI proved the application works again.`; s from click to banner: 30.0 (after R3b the banner text was changed to "Verified by EternalAI's own synthetic checkout" and the tagline to "Detect. Diagnose. Recover. Verify."; the R3b screenshots show the old wording)
- reveal: {'scenario': 'crash', 'target': 'orders', 'detected': True, 'time_to_detect_s': 4.8, 'recovered': True, 'time_to_verified_recovery_s': 41.6, 'failed_request_pct': 10.81, 'incidents_opened': 1, 'actions_executed': 1, 'abstained_correctly': None, 'harmful_interventions': 0}
- free RAM after: 2.88 GB
- screenshots: docs/screenshots/r3b_approve_1_card_full.png, docs/screenshots/r3b_approve_1_card.png, docs/screenshots/r3b_approve_1_causes.png, docs/screenshots/r3b_approve_2_banner_full.png, docs/screenshots/r3b_approve_2_banner.png

### Reject path (draw 1)

- card read from the page: `low riskclear_temp_path → orders | ask-first: low-risk action requires approval | orders shows signs of disk fill (classifier confidence 1.00). Proposed runbook: clear_temp_path. Recovery is only confirmed after the synthetic checkout passes. | ApproveReject`
- anomalous services when the card appeared: orders
- s from fault injection to card: at least 18.6; s from card to click: 0.6; message after click: `Done.`
- s from the challenge start to card: 64.6 (includes the evaluator's settle wait before injecting: 45 s, or 200 s after a release change)
- incident status after reject: escalated; actions: [{'runbook_id': 'clear_temp_path', 'service': 'orders', 'verdict': 'rejected_by_dashboard', 'executed': False}]
- reveal: {'scenario': 'disk_fill', 'target': 'orders', 'detected': True, 'time_to_detect_s': 8.7, 'recovered': False, 'time_to_verified_recovery_s': None, 'failed_request_pct': 8.7, 'incidents_opened': 1, 'actions_executed': 0, 'abstained_correctly': None, 'harmful_interventions': 0}
- free RAM after: 2.8 GB
- screenshots: docs/screenshots/r3b_reject_1_card_full.png, docs/screenshots/r3b_reject_1_card.png, docs/screenshots/r3b_reject_1_causes.png, docs/screenshots/r3b_reject_2_after_full.png

### Unseen fault (cpu_burn, ask-first)

- approval card: none
- report panel: `ReactiveescalatedInsufficient evidence: no automatic action proposed. |  | The inventory service exhibits significant latency with a latency ratio of 233.6, while other metrics remain stable. There are no associated error logs or memory issues for the inventory service. |  | Likely cause: insufficient evidence (no probability shown: the system abstained) | Proposed runbook: - | Report written by: gemini (LLM disagreed; engine diagnosis kept)`
- causes margin: `Margin between top two causes: 0.93`
- incidents: [{'id': '94fd1639', 'status': 'escalated', 'likely_cause': 'disk_fill', 'abstained': False, 'services': ['orders'], 'ranking': [{'service': 'orders', 'score': 0.9904171432807137}, {'service': 'web', 'score': 0.0036765614029487465}, {'service': 'inventory', 'score': 0.0029531476581688143}, {'service': 'payments', 'score': 0.0029531476581688143}]}, {'id': '6cfd9b6e', 'status': 'escalated', 'likely_cause': 'insufficient_evidence', 'abstained': True, 'services': ['web'], 'ranking': [{'service': 'orders', 'score': 0.9829679198150526}, {'service': 'web', 'score': 0.009222803130952277}, {'service': 'inventory', 'score': 0.004471225860530808}, {'service': 'payments', 'score': 0.0033380511934643395}]}, {'id': '539eaa7e', 'status': 'escalated', 'likely_cause': 'insufficient_evidence', 'abstained': True, 'services': ['inventory', 'orders', 'web'], 'ranking': [{'service': 'inventory', 'score': 0.9572569803457646}, {'service': 'orders', 'score': 0.031629711407819616}, {'service': 'web', 'score': 0.008241245286087079}, {'service': 'payments', 'score': 0.0028720629603286433}]}]
- reveal: {'scenario': 'cpu_burn', 'target': 'inventory', 'detected': True, 'time_to_detect_s': 6.8, 'recovered': False, 'time_to_verified_recovery_s': None, 'failed_request_pct': 0.0, 'incidents_opened': 1, 'actions_executed': 0, 'abstained_correctly': True, 'harmful_interventions': 0}
- free RAM after: 2.82 GB
- screenshots: docs/screenshots/r3b_unseen_1_full.png, docs/screenshots/r3b_unseen_1_report.png, docs/screenshots/r3b_unseen_1_causes.png, docs/screenshots/r3b_unseen_1_map.png
