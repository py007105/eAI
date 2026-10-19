# Multiple incidents or actions for one fault (evaluated v2 supported-fault runs, script output)

Rows examined: 36 (autopilot and ask-first, six supported fault types). 'More than one incident' = `incidents_opened` > 1; 'more than one action' = `actions_executed` > 1.

| arm | scenario | runs | runs with >1 incident | runs with >1 executed action | seeds affected | runbooks executed in affected runs |
|---|---|---|---|---|---|---|
| eternalai_autopilot | crash | 3 | 0 | 0 | - | - |
| eternalai_autopilot | latency | 3 | 0 | 0 | - | - |
| eternalai_autopilot | error_spike | 3 | 0 | 0 | - | - |
| eternalai_autopilot | memory_leak | 3 | 0 | 0 | - | - |
| eternalai_autopilot | disk_fill | 3 | 1 | 1 | 414 | clear_temp_path@inventory |
| eternalai_autopilot | bad_deploy | 3 | 0 | 0 | - | - |
| eternalai_ask_first | crash | 3 | 0 | 0 | - | - |
| eternalai_ask_first | latency | 3 | 0 | 0 | - | - |
| eternalai_ask_first | error_spike | 3 | 0 | 0 | - | - |
| eternalai_ask_first | memory_leak | 3 | 0 | 0 | - | - |
| eternalai_ask_first | disk_fill | 3 | 1 | 1 | 414 | clear_temp_path@inventory |
| eternalai_ask_first | bad_deploy | 3 | 0 | 0 | - | - |

Total: 2 runs with more than one incident and 2 runs with more than one executed action, of 36 fault runs.
