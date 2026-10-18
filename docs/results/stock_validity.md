# Stock-out validity check (script output)

Inventory logs: the container logs were lost to recreations by runbooks and Prometheus keeps 2 h, so there is no stock timeline; the evidence below is what the result rows, the run files and the orders table still hold. Where a dataset has no direct record this is said.

## v2 Stage 3 (95 rows)

- verification probes recorded: 36; with HTTP 409: 32; with success_rate > 0: 3
- last verification with a successful checkout: 2026-10-18 23:30:36 (eternalai_ask_first crash 200)
- first verification with HTTP 409: 2026-10-18 23:39:28 (eternalai_ask_first disk_fill 204)
- successes after the first 409: 0
- Because stock never rises, sku-mug had stock at every time up to 2026-10-18 23:30:36. Other SKUs: no direct evidence; loadgen picks SKUs uniformly, so they follow the same curve within the random difference between SKUs (see orders totals below).
- rows finished before the first 409: 59 (healthy 56, fault 3); after: 36 (healthy 0, fault 36)

- healthy rows: 56; failed_request_pct mean 0.56, max 4.42; rows with failed_request_pct >= 5: 0
- healthy rows by finish time, mean failed_request_pct: first 18 = 0.69, last 18 = 0.39 (a stock-out would raise it)

### Rows finishing after the first 409 (fault rows; failed_request_pct and detection inputs are confounded)

| arm | scenario | seed | finished (IST) | recovered | verification |
|---|---|---|---|---|---|
| eternalai_ask_first | disk_fill | 204 | 2026-10-18T23:39:41 | False | HTTP 409 |
| eternalai_ask_first | memory_leak | 203 | 2026-10-18T23:41:34 | False | HTTP 409 |
| eternalai_ask_first | latency | 201 | 2026-10-18T23:43:23 | False | HTTP 409 |
| eternalai_ask_first | memory_leak | 213 | 2026-10-18T23:45:12 | False | HTTP 409 |
| eternalai_ask_first | crash | 210 | 2026-10-18T23:46:58 | False | HTTP 409 |
| eternalai_ask_first | bad_deploy | 215 | 2026-10-18T23:49:03 | False | HTTP 409 |
| eternalai_ask_first | error_spike | 212 | 2026-10-18T23:53:27 | False | HTTP 409 |
| eternalai_ask_first | latency | 211 | 2026-10-18T23:55:16 | False | HTTP 409 |
| eternalai_ask_first | disk_fill | 214 | 2026-10-18T23:56:59 | False | HTTP 409 |
| eternalai_ask_first | bad_deploy | 225 | 2026-10-18T23:59:03 | False | HTTP 409 |
| eternalai_ask_first | memory_leak | 223 | 2026-10-19T00:03:24 | False | HTTP 409 |
| eternalai_ask_first | crash | 220 | 2026-10-19T00:05:10 | False | HTTP 409 |
| eternalai_ask_first | error_spike | 222 | 2026-10-19T00:06:57 | False | HTTP 409 |
| eternalai_ask_first | disk_fill | 224 | 2026-10-19T00:08:40 | False | HTTP 409 |
| eternalai_ask_first | latency | 221 | 2026-10-19T00:10:29 | False | HTTP 409 |
| eternalai_autopilot | crash | 200 | 2026-10-19T00:12:33 | False | HTTP 409 |
| eternalai_autopilot | disk_fill | 204 | 2026-10-19T00:14:11 | False | HTTP 409 |
| eternalai_autopilot | error_spike | 202 | 2026-10-19T00:15:51 | False | HTTP 409 |
| eternalai_autopilot | cpu_burn | 206 | 2026-10-19T00:17:10 | False | none |
| eternalai_autopilot | bad_deploy | 205 | 2026-10-19T00:19:11 | False | HTTP 409 |
| eternalai_autopilot | memory_leak | 203 | 2026-10-19T00:23:30 | False | HTTP 409 |
| eternalai_autopilot | latency | 201 | 2026-10-19T00:25:16 | False | HTTP 409 |
| eternalai_autopilot | memory_leak | 213 | 2026-10-19T00:27:02 | False | HTTP 409 |
| eternalai_autopilot | crash | 210 | 2026-10-19T00:28:43 | False | HTTP 409 |
| eternalai_autopilot | bad_deploy | 215 | 2026-10-19T00:30:41 | False | HTTP 409 |
| eternalai_autopilot | error_spike | 212 | 2026-10-19T00:34:56 | False | HTTP 409 |
| eternalai_autopilot | cpu_burn | 216 | 2026-10-19T00:36:49 | False | ReadTimeout |
| eternalai_autopilot | latency | 211 | 2026-10-19T00:39:04 | False | HTTP 409 |
| eternalai_autopilot | disk_fill | 214 | 2026-10-19T00:40:20 | False | none |
| eternalai_autopilot | cpu_burn | 226 | 2026-10-19T00:41:39 | False | none |
| eternalai_autopilot | memory_leak | 223 | 2026-10-19T00:43:19 | False | HTTP 409 |
| eternalai_autopilot | crash | 220 | 2026-10-19T00:44:59 | False | HTTP 409 |
| eternalai_autopilot | error_spike | 222 | 2026-10-19T00:46:42 | False | HTTP 409 |
| eternalai_autopilot | disk_fill | 224 | 2026-10-19T00:48:20 | False | HTTP 409 |
| eternalai_autopilot | bad_deploy | 225 | 2026-10-19T00:50:18 | False | HTTP 409 |
| eternalai_autopilot | latency | 221 | 2026-10-19T00:54:39 | False | HTTP 409 |

## v1 benchmark (225 rows, finished 2026-10-17T21:24:42 to 2026-10-18T09:57:29)

- verification probes recorded: 74; with HTTP 409: 0
- healthy rows: 50; failed_request_pct mean 3.44, max 18.40; rows with >= 5: 8
- healthy rows by finish time, mean failed_request_pct: first 16 = 6.03, last 16 = 2.31
- the v1 stack was the same volume, so the last v1 row finishing earlier than the Stage 3 last-good-probe time, with stock never rising, bounds v1 only for sku-mug (see the v2 section); other SKUs are covered by the healthy-row evidence above.

## original 72 training runs (72 runs, pre-injection window of each; 2026-10-17 00:35:34 to 2026-10-17 16:39:10 IST)

- web error ratio: mean 0.086, max 0.387; runs with web ratio >= 0.5: 0
- inventory error ratio: mean 0.026, max 0.324; runs with inventory ratio > 0.01: 13; > 0.5: 0
- runs with inventory ratio > 0.01 in time order: latency_1001 (10-17 00:41), error_spike_1002 (10-17 00:48), crash_1000 (10-17 00:49), good_deploy_1008 (10-17 00:51), traffic_surge_1207 (10-17 01:22), traffic_surge_1307 (10-17 01:48), memory_leak_1303 (10-17 01:50), crash_1400 (10-17 02:06), bad_deploy_1605 (10-17 14:53), bad_deploy_1705 (10-17 15:28), latency_1201 (10-17 16:26), cpu_burn_1406 (10-17 16:30), traffic_surge_1507 (10-17 16:32)
- a persistent stock-out would show as inventory/web error ratios that stay high in every later run; sporadic ones are other causes (a fault left from the previous run, a restart).

## 34 fresh runs (Stage 1) (34 runs, pre-injection window of each; 2026-10-18 16:11:22 to 2026-10-18 19:59:26 IST)

- web error ratio: mean 0.027, max 0.213; runs with web ratio >= 0.5: 0
- inventory error ratio: mean 0.000, max 0.000; runs with inventory ratio > 0.01: 0; > 0.5: 0
- runs with inventory ratio > 0.01 in time order: none
- a persistent stock-out would show as inventory/web error ratios that stay high in every later run; sporadic ones are other causes (a fault left from the previous run, a restart).

## Consumption record (live query)

- inventory volume created: 2026-10-16T17:31:30Z
- orders table, (sku, confirmed orders, units) over the whole volume lifetime: [('sku-bag', 48814, 97567), ('sku-book', 48860, 97862), ('sku-lamp', 49026, 97764), ('sku-mug', 50040, 97651)]
- inventory stock now (sku, stock): [('sku-lamp', 0), ('sku-mug', 0), ('sku-bag', 0), ('sku-book', 0)]
