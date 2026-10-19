# v2 pass criteria (applied mechanically; Amendment 4 section N, demo rule P)

Run counts found vs the plan: autopilot healthy 24/24; threshold healthy 24/24; ask-first healthy 8/8; ask-first supported 18/18; autopilot supported 18/18; autopilot cpu_burn 3/3

| # | criterion | verdict | counts |
|---|---|---|---|
| 1 | ask-first: approve_failures == 0, thread_errors == 0, all 18 supported detected, >= 15/18 recovered | **FAIL** | runs 26; approve_failures 0; thread_errors 0; rows without approver stats 0; detected 18/18; recovered 3/18 |
| 2 | autopilot healthy: <= 2/24 runs open an incident and no more than threshold_restart on the same seeds | **PASS** | autopilot 1/24; threshold_restart 6/24 (on autopilot's incident seeds: 6) |
| 3 | 0 executed actions in the 24 autopilot and 8 ask-first healthy runs | **PASS** | autopilot runs with an action 0/24; ask-first 0/8 |
| 4 | autopilot supported: all 18 detected and mean detection <= 15.1 s | **PASS** | detected 18/18; mean detection 12.36 s |
| 5 | autopilot supported: >= 15/18 recovered, no cell below 2/3 (crash 1/3) | **FAIL** | recovered 0/18; cells crash 0/3, latency 0/3, error_spike 0/3, memory_leak 0/3, disk_fill 0/3, bad_deploy 0/3; below minimum: ['crash', 'latency', 'error_spike', 'memory_leak', 'disk_fill', 'bad_deploy'] |
| 6 | autopilot supported: pooled mean failed-request % <= 23.4 | **FAIL** | mean 28.40% over 18 runs |
| 7 | cpu_burn: abstained correctly in >= 2 of 3 | **PASS** | abstained 2/3 |

**Demo decision (rule P):** at least one criterion FAILS: per rule P the demo uses v1 with its issues stated plainly. Failed criteria are reported as failed.
