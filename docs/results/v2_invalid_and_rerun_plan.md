# v2 row validity and re-run plan (script output; Amendment 8)

- last probe that completed a checkout (cutoff): 2026-10-18 23:30:36 IST (epoch 1792346436.354)
- first probe answered HTTP 409: 2026-10-18 23:39:28 IST
- rows in the raw file: 95; invalid by the rule (run end after the cutoff): 37; valid: 58

## Invalid rows (every one is listed; the originals stay in the file)

| arm | scenario | seed | run end (IST) | seconds after cutoff | recovered | verification |
|---|---|---|---|---|---|---|
| eternalai_ask_first | crash | 200 | 2026-10-18 23:30:44 | 8.4 | True | HTTP 200 |
| eternalai_ask_first | disk_fill | 204 | 2026-10-18 23:39:37 | 540.8 | False | HTTP 409 |
| eternalai_ask_first | memory_leak | 203 | 2026-10-18 23:41:28 | 651.9 | False | HTTP 409 |
| eternalai_ask_first | latency | 201 | 2026-10-18 23:43:20 | 764.2 | False | HTTP 409 |
| eternalai_ask_first | memory_leak | 213 | 2026-10-18 23:45:07 | 871.1 | False | HTTP 409 |
| eternalai_ask_first | crash | 210 | 2026-10-18 23:46:54 | 977.7 | False | HTTP 409 |
| eternalai_ask_first | bad_deploy | 215 | 2026-10-18 23:48:58 | 1101.8 | False | HTTP 409 |
| eternalai_ask_first | error_spike | 212 | 2026-10-18 23:53:20 | 1364.6 | False | HTTP 409 |
| eternalai_ask_first | latency | 211 | 2026-10-18 23:55:11 | 1475.3 | False | HTTP 409 |
| eternalai_ask_first | disk_fill | 214 | 2026-10-18 23:56:54 | 1578.3 | False | HTTP 409 |
| eternalai_ask_first | bad_deploy | 225 | 2026-10-18 23:58:57 | 1701.1 | False | HTTP 409 |
| eternalai_ask_first | memory_leak | 223 | 2026-10-19 00:03:20 | 1964.5 | False | HTTP 409 |
| eternalai_ask_first | crash | 220 | 2026-10-19 00:05:04 | 2068.5 | False | HTTP 409 |
| eternalai_ask_first | error_spike | 222 | 2026-10-19 00:06:53 | 2176.7 | False | HTTP 409 |
| eternalai_ask_first | disk_fill | 224 | 2026-10-19 00:08:35 | 2278.9 | False | HTTP 409 |
| eternalai_ask_first | latency | 221 | 2026-10-19 00:10:25 | 2389.4 | False | HTTP 409 |
| eternalai_autopilot | crash | 200 | 2026-10-19 00:12:28 | 2511.8 | False | HTTP 409 |
| eternalai_autopilot | disk_fill | 204 | 2026-10-19 00:14:06 | 2609.9 | False | HTTP 409; None |
| eternalai_autopilot | error_spike | 202 | 2026-10-19 00:15:47 | 2711.1 | False | HTTP 409 |
| eternalai_autopilot | cpu_burn | 206 | 2026-10-19 00:17:00 | 2784.5 | False | None |
| eternalai_autopilot | bad_deploy | 205 | 2026-10-19 00:19:05 | 2909.4 | False | HTTP 409 |
| eternalai_autopilot | memory_leak | 203 | 2026-10-19 00:23:26 | 3170.5 | False | HTTP 409 |
| eternalai_autopilot | latency | 201 | 2026-10-19 00:25:10 | 3274.5 | False | HTTP 409 |
| eternalai_autopilot | memory_leak | 213 | 2026-10-19 00:26:56 | 3380.6 | False | HTTP 409 |
| eternalai_autopilot | crash | 210 | 2026-10-19 00:28:37 | 3481.6 | False | HTTP 409 |
| eternalai_autopilot | bad_deploy | 215 | 2026-10-19 00:30:37 | 3600.7 | False | HTTP 409 |
| eternalai_autopilot | error_spike | 212 | 2026-10-19 00:34:52 | 3855.9 | False | HTTP 409 |
| eternalai_autopilot | cpu_burn | 216 | 2026-10-19 00:36:38 | 3962.4 | False | ReadTimeout; None |
| eternalai_autopilot | latency | 211 | 2026-10-19 00:38:58 | 4102.5 | False | HTTP 409 |
| eternalai_autopilot | disk_fill | 214 | 2026-10-19 00:40:14 | 4177.7 | False | None |
| eternalai_autopilot | cpu_burn | 226 | 2026-10-19 00:41:30 | 4254.1 | False | None |
| eternalai_autopilot | memory_leak | 223 | 2026-10-19 00:43:15 | 4359.4 | False | HTTP 409 |
| eternalai_autopilot | crash | 220 | 2026-10-19 00:44:54 | 4458.3 | False | HTTP 409 |
| eternalai_autopilot | error_spike | 222 | 2026-10-19 00:46:36 | 4560.3 | False | HTTP 409 |
| eternalai_autopilot | disk_fill | 224 | 2026-10-19 00:48:15 | 4658.9 | False | HTTP 409 |
| eternalai_autopilot | bad_deploy | 225 | 2026-10-19 00:50:13 | 4777.4 | False | HTTP 409 |
| eternalai_autopilot | latency | 221 | 2026-10-19 00:54:34 | 5037.7 | False | HTTP 409 |

## Valid rows that finish closest before the cutoff

| arm | scenario | seed | run end (IST) | seconds before cutoff |
|---|---|---|---|---|
| eternalai_ask_first | bad_deploy | 205 | 2026-10-18 23:26:26 | 249.9 |
| eternalai_ask_first | error_spike | 202 | 2026-10-18 23:24:19 | 376.5 |
| eternalai_ask_first | good_deploy | 238 | 2026-10-18 23:19:35 | 660.4 |
| eternalai_ask_first | traffic_surge | 237 | 2026-10-18 23:17:45 | 770.6 |
| eternalai_ask_first | traffic_surge | 227 | 2026-10-18 23:15:56 | 879.5 |

## Cell by cell (planned / found / valid / invalid / re-run)

| arm | scenario | planned | found | valid | invalid | re-run |
|---|---|---|---|---|---|---|
| eternalai_autopilot | crash | 3 | 3 | 0 | 3 | 3 |
| eternalai_autopilot | latency | 3 | 3 | 0 | 3 | 3 |
| eternalai_autopilot | error_spike | 3 | 3 | 0 | 3 | 3 |
| eternalai_autopilot | memory_leak | 3 | 3 | 0 | 3 | 3 |
| eternalai_autopilot | disk_fill | 3 | 3 | 0 | 3 | 3 |
| eternalai_autopilot | bad_deploy | 3 | 3 | 0 | 3 | 3 |
| eternalai_autopilot | cpu_burn | 3 | 3 | 0 | 3 | 3 |
| eternalai_autopilot | traffic_surge | 12 | 12 | 12 | 0 | 0 |
| eternalai_autopilot | good_deploy | 12 | 12 | 12 | 0 | 0 |
| threshold_restart | traffic_surge | 12 | 12 | 12 | 0 | 0 |
| threshold_restart | good_deploy | 12 | 12 | 12 | 0 | 0 |
| eternalai_ask_first | crash | 3 | 3 | 0 | 3 | 3 |
| eternalai_ask_first | latency | 3 | 3 | 0 | 3 | 3 |
| eternalai_ask_first | error_spike | 3 | 3 | 1 | 2 | 2 |
| eternalai_ask_first | memory_leak | 3 | 3 | 0 | 3 | 3 |
| eternalai_ask_first | disk_fill | 3 | 3 | 0 | 3 | 3 |
| eternalai_ask_first | bad_deploy | 3 | 3 | 1 | 2 | 2 |
| eternalai_ask_first | traffic_surge | 4 | 4 | 4 | 0 | 0 |
| eternalai_ask_first | good_deploy | 4 | 4 | 4 | 0 | 0 |
| **total** | | 95 | 95 | 58 | 37 | 37 |

## Re-run jobs in the pre-registered order

| # | segment | arm | scenario | seed | kind | replaces seed |
|---|---|---|---|---|---|---|
| 1 | P2 | eternalai_ask_first | crash | 400 | fresh | 200 |
| 2 | P2 | eternalai_ask_first | latency | 401 | fresh | 201 |
| 3 | P2 | eternalai_ask_first | error_spike | 402 | fresh | 212 |
| 4 | P2 | eternalai_ask_first | memory_leak | 403 | fresh | 203 |
| 5 | P2 | eternalai_ask_first | disk_fill | 404 | fresh | 204 |
| 6 | P2 | eternalai_ask_first | bad_deploy | 405 | fresh | 215 |
| 7 | P2 | eternalai_ask_first | crash | 410 | fresh | 210 |
| 8 | P2 | eternalai_ask_first | latency | 411 | fresh | 211 |
| 9 | P2 | eternalai_ask_first | error_spike | 412 | fresh | 222 |
| 10 | P2 | eternalai_ask_first | memory_leak | 413 | fresh | 213 |
| 11 | P2 | eternalai_ask_first | disk_fill | 414 | fresh | 214 |
| 12 | P2 | eternalai_ask_first | bad_deploy | 415 | fresh | 225 |
| 13 | P2 | eternalai_ask_first | crash | 420 | fresh | 220 |
| 14 | P2 | eternalai_ask_first | latency | 421 | fresh | 221 |
| 15 | P2 | eternalai_ask_first | memory_leak | 423 | fresh | 223 |
| 16 | P2 | eternalai_ask_first | disk_fill | 424 | fresh | 224 |
| 17 | P3 | eternalai_autopilot | error_spike | 202 | same-seed | 202 |
| 18 | P3 | eternalai_autopilot | bad_deploy | 205 | same-seed | 205 |
| 19 | P3 | eternalai_autopilot | crash | 400 | fresh | 200 |
| 20 | P3 | eternalai_autopilot | latency | 401 | fresh | 201 |
| 21 | P3 | eternalai_autopilot | error_spike | 402 | fresh | 212 |
| 22 | P3 | eternalai_autopilot | memory_leak | 403 | fresh | 203 |
| 23 | P3 | eternalai_autopilot | disk_fill | 404 | fresh | 204 |
| 24 | P3 | eternalai_autopilot | bad_deploy | 405 | fresh | 215 |
| 25 | P3 | eternalai_autopilot | cpu_burn | 406 | fresh | 206 |
| 26 | P3 | eternalai_autopilot | crash | 410 | fresh | 210 |
| 27 | P3 | eternalai_autopilot | latency | 411 | fresh | 211 |
| 28 | P3 | eternalai_autopilot | error_spike | 412 | fresh | 222 |
| 29 | P3 | eternalai_autopilot | memory_leak | 413 | fresh | 213 |
| 30 | P3 | eternalai_autopilot | disk_fill | 414 | fresh | 214 |
| 31 | P3 | eternalai_autopilot | bad_deploy | 415 | fresh | 225 |
| 32 | P3 | eternalai_autopilot | cpu_burn | 416 | fresh | 216 |
| 33 | P3 | eternalai_autopilot | crash | 420 | fresh | 220 |
| 34 | P3 | eternalai_autopilot | latency | 421 | fresh | 221 |
| 35 | P3 | eternalai_autopilot | memory_leak | 423 | fresh | 223 |
| 36 | P3 | eternalai_autopilot | disk_fill | 424 | fresh | 224 |
| 37 | P3 | eternalai_autopilot | cpu_burn | 426 | fresh | 226 |

Total re-run jobs: 37; same-seed 2; fresh-seed 35
