# Benchmark v1: triage of every non-recovery (rule-based; see `scripts/triage_nonrecoveries.py`)

72 non-recoveries on supported faults (arms other than no_action). Counts by arm and class:

| arm | a harness artifact | b system bug | c design limitation |
|---|---|---|---|
| eternalai_ask_first | 0 | 28 | 2 |
| eternalai_autopilot | 1 | 0 | 2 |
| prototype_rules | 5 | 0 | 16 |
| threshold_restart | 1 | 0 | 17 |

Every run, with its facts:

| arm | scenario | seed | class | evidence |
|---|---|---|---|---|
| eternalai_ask_first | bad_deploy | 105 | b | R1 stuck incident: an ask-first proposal stayed awaiting_approval (never approved) and, with no expiry, blocked every later detection in the arm; final=awaiting_approval; actions=['rollback_release@payments:needs_approval']; incidents=[('awaiting_approval', 'bad_deploy', False)] |
| eternalai_ask_first | bad_deploy | 115 | b | R1 stuck incident: undetected because an earlier proposal stayed awaiting_approval and blocked new incidents; final=undetected; actions=[]; incidents=[] |
| eternalai_ask_first | bad_deploy | 125 | b | R1 stuck incident: undetected because an earlier proposal stayed awaiting_approval and blocked new incidents; final=undetected; actions=[]; incidents=[] |
| eternalai_ask_first | bad_deploy | 135 | b | R1 stuck incident: undetected because an earlier proposal stayed awaiting_approval and blocked new incidents; final=undetected; actions=[]; incidents=[] |
| eternalai_ask_first | bad_deploy | 145 | b | R1 stuck incident: undetected because an earlier proposal stayed awaiting_approval and blocked new incidents; final=undetected; actions=[]; incidents=[] |
| eternalai_ask_first | crash | 100 | c | R2 first incident abstained (insufficient_evidence) on a crash of orders; orders has 1 crash run in training; final=escalated; actions=[]; incidents=[('escalated', 'insufficient_evidence', True), ('open', 'pending', False)] |
| eternalai_ask_first | crash | 110 | b | R1 stuck incident: undetected because an earlier proposal stayed awaiting_approval and blocked new incidents; final=undetected; actions=[]; incidents=[] |
| eternalai_ask_first | crash | 120 | b | R1 stuck incident: undetected because an earlier proposal stayed awaiting_approval and blocked new incidents; final=undetected; actions=[]; incidents=[] |
| eternalai_ask_first | crash | 130 | b | R1 stuck incident: undetected because an earlier proposal stayed awaiting_approval and blocked new incidents; final=undetected; actions=[]; incidents=[] |
| eternalai_ask_first | crash | 140 | b | R1 stuck incident: undetected because an earlier proposal stayed awaiting_approval and blocked new incidents; final=undetected; actions=[]; incidents=[] |
| eternalai_ask_first | disk_fill | 104 | c | R6 the arm acted or escalated and the fault was not reported recovered; final=escalated; actions=[]; incidents=[('escalated', 'insufficient_evidence', True)] |
| eternalai_ask_first | disk_fill | 114 | b | R1 stuck incident: undetected because an earlier proposal stayed awaiting_approval and blocked new incidents; final=undetected; actions=[]; incidents=[] |
| eternalai_ask_first | disk_fill | 124 | b | R1 stuck incident: undetected because an earlier proposal stayed awaiting_approval and blocked new incidents; final=undetected; actions=[]; incidents=[] |
| eternalai_ask_first | disk_fill | 134 | b | R1 stuck incident: undetected because an earlier proposal stayed awaiting_approval and blocked new incidents; final=undetected; actions=[]; incidents=[] |
| eternalai_ask_first | disk_fill | 144 | b | R1 stuck incident: undetected because an earlier proposal stayed awaiting_approval and blocked new incidents; final=undetected; actions=[]; incidents=[] |
| eternalai_ask_first | error_spike | 102 | b | R1 stuck incident: undetected because an earlier proposal stayed awaiting_approval and blocked new incidents; final=undetected; actions=[]; incidents=[] |
| eternalai_ask_first | error_spike | 112 | b | R1 stuck incident: undetected because an earlier proposal stayed awaiting_approval and blocked new incidents; final=undetected; actions=[]; incidents=[] |
| eternalai_ask_first | error_spike | 122 | b | R1 stuck incident: undetected because an earlier proposal stayed awaiting_approval and blocked new incidents; final=undetected; actions=[]; incidents=[] |
| eternalai_ask_first | error_spike | 132 | b | R1 stuck incident: undetected because an earlier proposal stayed awaiting_approval and blocked new incidents; final=undetected; actions=[]; incidents=[] |
| eternalai_ask_first | error_spike | 142 | b | R1 stuck incident: undetected because an earlier proposal stayed awaiting_approval and blocked new incidents; final=undetected; actions=[]; incidents=[] |
| eternalai_ask_first | latency | 101 | b | R1 stuck incident: undetected because an earlier proposal stayed awaiting_approval and blocked new incidents; final=undetected; actions=[]; incidents=[] |
| eternalai_ask_first | latency | 111 | b | R1 stuck incident: undetected because an earlier proposal stayed awaiting_approval and blocked new incidents; final=undetected; actions=[]; incidents=[] |
| eternalai_ask_first | latency | 121 | b | R1 stuck incident: undetected because an earlier proposal stayed awaiting_approval and blocked new incidents; final=undetected; actions=[]; incidents=[] |
| eternalai_ask_first | latency | 131 | b | R1 stuck incident: undetected because an earlier proposal stayed awaiting_approval and blocked new incidents; final=undetected; actions=[]; incidents=[] |
| eternalai_ask_first | latency | 141 | b | R1 stuck incident: undetected because an earlier proposal stayed awaiting_approval and blocked new incidents; final=undetected; actions=[]; incidents=[] |
| eternalai_ask_first | memory_leak | 103 | b | R1 stuck incident: undetected because an earlier proposal stayed awaiting_approval and blocked new incidents; final=undetected; actions=[]; incidents=[] |
| eternalai_ask_first | memory_leak | 113 | b | R1 stuck incident: undetected because an earlier proposal stayed awaiting_approval and blocked new incidents; final=undetected; actions=[]; incidents=[] |
| eternalai_ask_first | memory_leak | 123 | b | R1 stuck incident: undetected because an earlier proposal stayed awaiting_approval and blocked new incidents; final=undetected; actions=[]; incidents=[] |
| eternalai_ask_first | memory_leak | 133 | b | R1 stuck incident: undetected because an earlier proposal stayed awaiting_approval and blocked new incidents; final=undetected; actions=[]; incidents=[] |
| eternalai_ask_first | memory_leak | 143 | b | R1 stuck incident: undetected because an earlier proposal stayed awaiting_approval and blocked new incidents; final=undetected; actions=[]; incidents=[] |
| eternalai_autopilot | crash | 100 | c | R2 first incident abstained (insufficient_evidence) on a crash of orders; orders has 1 crash run in training; final=escalated; actions=[]; incidents=[('escalated', 'insufficient_evidence', True), ('open', 'pending', False)] |
| eternalai_autopilot | crash | 120 | c | R2 first incident abstained (insufficient_evidence) on a crash of orders; orders has 1 crash run in training; final=escalated; actions=[]; incidents=[('escalated', 'insufficient_evidence', True), ('open', 'pending', False)] |
| eternalai_autopilot | crash | 130 | a | R3 restart blocked by a cooldown left by an action in an earlier run (the brain is not reset between runs); final=escalated; actions=['restart_service@inventory:blocked']; incidents=[('escalated', 'down', False)] |
| prototype_rules | bad_deploy | 105 | c | R5 no incident was ever opened by this arm's detector; final=undetected; actions=[]; incidents=[] |
| prototype_rules | bad_deploy | 115 | a | R4 the run window ended while the incident was still 'executing'; final=executing; actions=['restart_service@orders:execute']; incidents=[('recovered', 'memory_leak', False), ('open', 'pending', False)] |
| prototype_rules | bad_deploy | 145 | a | R3 restart blocked by a cooldown left by an action in an earlier run (the brain is not reset between runs); final=escalated; actions=['rollback_release@inventory:blocked']; incidents=[('escalated', 'bad_deploy', False)] |
| prototype_rules | crash | 120 | a | R3 restart blocked by a cooldown left by an action in an earlier run (the brain is not reset between runs); final=escalated; actions=['restart_service@orders:blocked']; incidents=[('escalated', 'down', False)] |
| prototype_rules | crash | 140 | c | R6 the arm acted or escalated and the fault was not reported recovered; final=escalated; actions=['restart_service@web:blocked']; incidents=[('escalated', 'down', False), ('open', 'pending', False)] |
| prototype_rules | disk_fill | 124 | c | R6 the arm acted or escalated and the fault was not reported recovered; final=escalated; actions=['restart_service@web:blocked']; incidents=[('escalated', 'memory_leak', False)] |
| prototype_rules | disk_fill | 134 | c | R6 the arm acted or escalated and the fault was not reported recovered; final=escalated; actions=['restart_service@web:blocked']; incidents=[('escalated', 'memory_leak', False)] |
| prototype_rules | disk_fill | 144 | c | R6 the arm acted or escalated and the fault was not reported recovered; final=escalated; actions=['restart_service@web:blocked']; incidents=[('escalated', 'memory_leak', False)] |
| prototype_rules | error_spike | 112 | c | R6 the arm acted or escalated and the fault was not reported recovered; final=unresolved; actions=['restart_service@orders:execute']; incidents=[('unresolved', 'memory_leak', False)] |
| prototype_rules | error_spike | 122 | c | R5 no incident was ever opened by this arm's detector; final=undetected; actions=[]; incidents=[] |
| prototype_rules | error_spike | 132 | c | R6 the arm acted or escalated and the fault was not reported recovered; final=escalated; actions=['restart_service@web:blocked']; incidents=[('escalated', 'memory_leak', False)] |
| prototype_rules | error_spike | 142 | c | R5 no incident was ever opened by this arm's detector; final=undetected; actions=[]; incidents=[] |
| prototype_rules | latency | 101 | a | R4 the run window ended while the incident was still 'verifying'; final=verifying; actions=['restart_service@orders:execute']; incidents=[('recovered', 'memory_leak', False), ('open', 'pending', False)] |
| prototype_rules | latency | 111 | c | R6 the arm acted or escalated and the fault was not reported recovered; final=escalated; actions=['restart_service@web:blocked']; incidents=[('escalated', 'memory_leak', False), ('open', 'pending', False)] |
| prototype_rules | latency | 121 | c | R6 the arm acted or escalated and the fault was not reported recovered; final=escalated; actions=['restart_service@web:blocked']; incidents=[('escalated', 'memory_leak', False)] |
| prototype_rules | latency | 131 | a | R4 the run window ended while the incident was still 'open'; final=open; actions=['restart_service@web:blocked']; incidents=[('escalated', 'memory_leak', False)] |
| prototype_rules | latency | 141 | c | R5 no incident was ever opened by this arm's detector; final=undetected; actions=[]; incidents=[] |
| prototype_rules | memory_leak | 113 | c | R6 the arm acted or escalated and the fault was not reported recovered; final=escalated; actions=['restart_service@web:blocked']; incidents=[('escalated', 'memory_leak', False)] |
| prototype_rules | memory_leak | 123 | c | R6 the arm acted or escalated and the fault was not reported recovered; final=escalated; actions=['restart_service@web:blocked']; incidents=[('escalated', 'memory_leak', False)] |
| prototype_rules | memory_leak | 133 | c | R5 no incident was ever opened by this arm's detector; final=undetected; actions=[]; incidents=[] |
| prototype_rules | memory_leak | 143 | c | R6 the arm acted or escalated and the fault was not reported recovered; final=escalated; actions=['restart_service@web:blocked']; incidents=[('escalated', 'memory_leak', False)] |
| threshold_restart | bad_deploy | 105 | c | R6 the arm acted or escalated and the fault was not reported recovered; final=unresolved; actions=['restart_service@payments:execute']; incidents=[('unresolved', 'insufficient_evidence', False)] |
| threshold_restart | bad_deploy | 115 | c | R6 the arm acted or escalated and the fault was not reported recovered; final=unresolved; actions=['restart_service@payments:execute']; incidents=[('unresolved', 'insufficient_evidence', False)] |
| threshold_restart | bad_deploy | 125 | c | R6 the arm acted or escalated and the fault was not reported recovered; final=unresolved; actions=['restart_service@orders:execute']; incidents=[('unresolved', 'insufficient_evidence', False)] |
| threshold_restart | bad_deploy | 135 | c | R6 the arm acted or escalated and the fault was not reported recovered; final=escalated; actions=['restart_service@payments:blocked']; incidents=[('escalated', 'insufficient_evidence', False)] |
| threshold_restart | bad_deploy | 145 | c | R6 the arm acted or escalated and the fault was not reported recovered; final=unresolved; actions=['restart_service@inventory:execute']; incidents=[('unresolved', 'insufficient_evidence', False)] |
| threshold_restart | crash | 140 | c | R6 the arm acted or escalated and the fault was not reported recovered; final=escalated; actions=['restart_service@web:blocked']; incidents=[('escalated', 'insufficient_evidence', False)] |
| threshold_restart | disk_fill | 104 | c | R5 no incident was ever opened by this arm's detector; final=undetected; actions=[]; incidents=[('open', 'pending', False)] |
| threshold_restart | disk_fill | 114 | c | R5 no incident was ever opened by this arm's detector; final=undetected; actions=[]; incidents=[] |
| threshold_restart | disk_fill | 124 | c | R6 the arm acted or escalated and the fault was not reported recovered; final=escalated; actions=['restart_service@payments:blocked']; incidents=[('escalated', 'insufficient_evidence', False)] |
| threshold_restart | disk_fill | 134 | c | R6 the arm acted or escalated and the fault was not reported recovered; final=unresolved; actions=['restart_service@web:execute']; incidents=[('unresolved', 'insufficient_evidence', False)] |
| threshold_restart | disk_fill | 144 | c | R6 the arm acted or escalated and the fault was not reported recovered; final=unresolved; actions=['restart_service@web:execute']; incidents=[('unresolved', 'insufficient_evidence', False)] |
| threshold_restart | error_spike | 142 | c | R6 the arm acted or escalated and the fault was not reported recovered; final=unresolved; actions=['restart_service@orders:execute']; incidents=[('unresolved', 'insufficient_evidence', False)] |
| threshold_restart | latency | 141 | c | R6 the arm acted or escalated and the fault was not reported recovered; final=escalated; actions=['restart_service@web:blocked']; incidents=[('escalated', 'insufficient_evidence', False)] |
| threshold_restart | memory_leak | 103 | c | R5 no incident was ever opened by this arm's detector; final=undetected; actions=[]; incidents=[] |
| threshold_restart | memory_leak | 113 | c | R5 no incident was ever opened by this arm's detector; final=undetected; actions=[]; incidents=[] |
| threshold_restart | memory_leak | 123 | c | R5 no incident was ever opened by this arm's detector; final=undetected; actions=[]; incidents=[] |
| threshold_restart | memory_leak | 133 | a | R4 the run window ended while the incident was still 'open'; final=open; actions=[]; incidents=[('escalated', 'insufficient_evidence', False)] |
| threshold_restart | memory_leak | 143 | c | R5 no incident was ever opened by this arm's detector; final=undetected; actions=[]; incidents=[] |
