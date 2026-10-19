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

## R3: human-driven, real browser

Not recorded yet.
