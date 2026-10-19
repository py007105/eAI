# v2 results (rendered by `scripts/render_v2_report.py`; every number comes from the exported rows)

Method, deviations and limitations: `docs/EVALUATION.md` (canonical). Wording rule: Amendment 6. These tables describe the **reduced v2 plan** (Amendment 4 section M) on seeds 200-318 and the replacement block 400-429 (Amendment 8). v1 and v2 are unpaired and use different seeds. No `no_action` or `prototype_rules` arm was run in v2, and `threshold_restart` was run only on healthy runs, so **v2 has no paired baseline comparison for supported faults**.

## 1. Run accounting

- evaluated set: **95** rows = **58 valid original** + **37 replacement (re-run)**
- original rows marked invalid by the Amendment 8 exclusion rule (run ended after the last confirmed in-stock checkout): **37** (kept in `benchmark_v2_raw.jsonl`, never deleted; listed in `invalid_rows.json`; every one is triage class a, harness/environment artifact)
- replacement jobs: 37; **2 reused the original seed** (the partner arm stayed valid) and **35 used fresh seeds** (19 distinct seeds, 400-426)
- the replacement runs were **designed after the stock-out was seen**; the exclusion rule is by stock timeline (timestamps), not by outcome, and was committed before any restock or re-run (Amendment 8)
- stock gate (re-runs only): 1 restock(s); lowest per-SKU stock after any re-run: 95230; re-run rows with a stock record: 37 of 37

## 2. Pre-registered criteria (Amendment 4 section N), script output

Run counts found vs the plan: autopilot healthy 24/24; threshold healthy 24/24; ask-first healthy 8/8; ask-first supported 18/18; autopilot supported 18/18; autopilot cpu_burn 3/3

| # | criterion | verdict | counts |
|---|---|---|---|
| 1 | ask-first: approve_failures == 0, thread_errors == 0, all 18 supported detected, >= 15/18 recovered | **PASS** | runs 26; approve_failures 0; thread_errors 0; rows without approver stats 0; detected 18/18; recovered 18/18 |
| 2 | autopilot healthy: <= 2/24 runs open an incident and no more than threshold_restart on the same seeds | **PASS** | autopilot 1/24; threshold_restart 6/24 (on autopilot's incident seeds: 6) |
| 3 | 0 executed actions in the 24 autopilot and 8 ask-first healthy runs | **PASS** | autopilot runs with an action 0/24; ask-first 0/8 |
| 4 | autopilot supported: all 18 detected and mean detection <= 15.1 s | **PASS** | detected 18/18; mean detection 11.78 s |
| 5 | autopilot supported: >= 15/18 recovered, no cell below 2/3 (crash 1/3) | **PASS** | recovered 18/18; cells crash 3/3, latency 3/3, error_spike 3/3, memory_leak 3/3, disk_fill 3/3, bad_deploy 3/3 |
| 6 | autopilot supported: pooled mean failed-request % <= 23.4 | **PASS** | mean 11.15% over 18 runs |
| 7 | cpu_burn: abstained correctly in >= 2 of 3 | **PASS** | abstained 2/3 |

**Demo decision (rule P):** all criteria PASS: per rule P the demo may show v2.

## 3. Per cell: sample sizes with Wilson 95% intervals

n is 3 per fault cell and 4-12 per healthy cell. With n = 3 a perfect cell (3/3) is still compatible with a true rate near 44%; a pooled 18/18 is compatible with a true rate down to about 82%. Treat these as 'no failure observed', not as a rate.

| arm | scenario | n | seeds | detected | recovered (self-verified) | failed-request % (values; mean) | incident opened | action executed | abstained correctly |
|---|---|---|---|---|---|---|---|---|---|
| eternalai_autopilot | crash | 3/3 | 400 410 420 | 3/3 [44%, 100%] | 3/3 [44%, 100%] | 10.7 8.4 31.3; 16.84 | 3/3 [44%, 100%] | 3/3 [44%, 100%] | - |
| eternalai_autopilot | latency | 3/3 | 401 411 421 | 3/3 [44%, 100%] | 3/3 [44%, 100%] | 5.4 0.7 1.5; 2.50 | 3/3 [44%, 100%] | 3/3 [44%, 100%] | - |
| eternalai_autopilot | error_spike | 3/3 | 202 402 412 | 3/3 [44%, 100%] | 3/3 [44%, 100%] | 21.7 17.8 8.9; 16.13 | 3/3 [44%, 100%] | 3/3 [44%, 100%] | - |
| eternalai_autopilot | memory_leak | 3/3 | 403 413 423 | 3/3 [44%, 100%] | 3/3 [44%, 100%] | 0.3 3.6 1.7; 1.89 | 3/3 [44%, 100%] | 3/3 [44%, 100%] | - |
| eternalai_autopilot | disk_fill | 3/3 | 404 414 424 | 3/3 [44%, 100%] | 3/3 [44%, 100%] | 0.0 0.0 0.0; 0.00 | 3/3 [44%, 100%] | 3/3 [44%, 100%] | - |
| eternalai_autopilot | bad_deploy | 3/3 | 205 405 415 | 3/3 [44%, 100%] | 3/3 [44%, 100%] | 41.2 37.5 10.0; 29.54 | 3/3 [44%, 100%] | 3/3 [44%, 100%] | - |
| eternalai_autopilot | cpu_burn | 3/3 | 406 416 426 | 3/3 [44%, 100%] | - | 68.2 0.0 27.7; 31.98 | 3/3 [44%, 100%] | 1/3 [6%, 79%] | 2/3 [21%, 94%] |
| eternalai_autopilot | traffic_surge | 12/12 | 207 217 227 237 247 257 267 277 287 297 307 317 | - | - | 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0; 0.00 | 1/12 [1%, 35%] | 0/12 [0%, 24%] | - |
| eternalai_autopilot | good_deploy | 12/12 | 208 218 228 238 248 258 268 278 288 298 308 318 | - | - | 1.7 0.8 2.2 0.5 1.4 4.4 0.3 0.6 0.6 0.5 1.2 2.7; 1.41 | 0/12 [0%, 24%] | 0/12 [0%, 24%] | - |
| threshold_restart | traffic_surge | 12/12 | 207 217 227 237 247 257 267 277 287 297 307 317 | - | - | 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0; 0.00 | 0/12 [0%, 24%] | 0/12 [0%, 24%] | - |
| threshold_restart | good_deploy | 12/12 | 208 218 228 238 248 258 268 278 288 298 308 318 | - | - | 0.5 0.5 1.1 1.1 1.4 1.5 1.1 0.6 1.0 1.8 0.3 1.8; 1.06 | 6/12 [25%, 75%] | 0/12 [0%, 24%] | - |
| eternalai_ask_first | crash | 3/3 | 400 410 420 | 3/3 [44%, 100%] | 3/3 [44%, 100%] | 15.0 14.9 32.5; 20.79 | 3/3 [44%, 100%] | 3/3 [44%, 100%] | - |
| eternalai_ask_first | latency | 3/3 | 401 411 421 | 3/3 [44%, 100%] | 3/3 [44%, 100%] | 2.7 1.1 0.5; 1.44 | 3/3 [44%, 100%] | 3/3 [44%, 100%] | - |
| eternalai_ask_first | error_spike | 3/3 | 202 402 412 | 3/3 [44%, 100%] | 3/3 [44%, 100%] | 29.5 29.0 6.2; 21.58 | 3/3 [44%, 100%] | 3/3 [44%, 100%] | - |
| eternalai_ask_first | memory_leak | 3/3 | 403 413 423 | 3/3 [44%, 100%] | 3/3 [44%, 100%] | 0.6 4.9 2.5; 2.67 | 3/3 [44%, 100%] | 3/3 [44%, 100%] | - |
| eternalai_ask_first | disk_fill | 3/3 | 404 414 424 | 3/3 [44%, 100%] | 3/3 [44%, 100%] | 0.0 0.0 1.1; 0.35 | 3/3 [44%, 100%] | 3/3 [44%, 100%] | - |
| eternalai_ask_first | bad_deploy | 3/3 | 205 405 415 | 3/3 [44%, 100%] | 3/3 [44%, 100%] | 47.4 42.4 12.9; 34.22 | 3/3 [44%, 100%] | 3/3 [44%, 100%] | - |
| eternalai_ask_first | traffic_surge | 4/4 | 207 217 227 237 | - | - | 0.0 0.0 0.0 0.0; 0.00 | 0/4 [0%, 49%] | 0/4 [0%, 49%] | - |
| eternalai_ask_first | good_deploy | 4/4 | 208 218 228 238 | - | - | 0.8 0.6 0.2 0.0; 0.40 | 0/4 [0%, 49%] | 0/4 [0%, 49%] | - |

## 4. Pooled counts with Wilson 95% intervals

| quantity | count [95% interval] | note |
|---|---|---|
| eternalai_autopilot: supported faults detected | 18/18 [82%, 100%] | 6 fault types x 3 seeds |
| eternalai_autopilot: supported faults recovered (own verification) | 18/18 [82%, 100%] | recovery is internally verified; see EVALUATION.md |
| eternalai_ask_first: supported faults detected | 18/18 [82%, 100%] | 6 fault types x 3 seeds |
| eternalai_ask_first: supported faults recovered (own verification) | 18/18 [82%, 100%] | recovery is internally verified; see EVALUATION.md |
| eternalai_autopilot: healthy runs that opened an incident | 1/24 [1%, 20%] | traffic_surge + good_deploy |
| eternalai_autopilot: healthy runs with an executed action | 0/24 [0%, 14%] | |
| threshold_restart: healthy runs that opened an incident | 6/24 [12%, 45%] | traffic_surge + good_deploy |
| threshold_restart: healthy runs with an executed action | 0/24 [0%, 14%] | |
| eternalai_ask_first: healthy runs that opened an incident | 0/8 [0%, 32%] | traffic_surge + good_deploy |
| eternalai_ask_first: healthy runs with an executed action | 0/8 [0%, 32%] | |
| eternalai_autopilot: cpu_burn abstained correctly | 2/3 [21%, 94%] | unseen fault; n = 3 |

Autopilot, 18 supported runs: mean failed-request % 11.15 (min 0.00, max 41.16); mean detection 11.78 s (min 4.0, max 26.0). No `no_action` run exists in v2, so the failed-request % has no same-seed reference.

## 5. cpu_burn rows (autopilot; unseen fault, no runbook)

| seed | target | abstained correctly | actions executed | scorer 'harmful' flag | final status | failed-request % |
|---|---|---|---|---|---|---|
| 406 | inventory | True | 0 | 0 | escalated | 68.22 |
| 416 | payments | True | 0 | 0 | escalated | 0.0 |
| 426 | orders | False | 1 | 1 | unresolved | 27.71 |

The scorer's 'harmful' flag only means an executed action on a service other than the injected target (`evaluator/scoring.py`); it is not a measurement of damage. Details: `docs/postmortems/cpu_burn_seed426.md`.

## 6. Replacement jobs (script output of the exclusion rule)

| arm | scenario | seed | kind |
|---|---|---|---|
| eternalai_autopilot | error_spike | 202 | same-seed |
| eternalai_autopilot | bad_deploy | 205 | same-seed |
| eternalai_ask_first | crash | 400 | fresh |
| eternalai_autopilot | crash | 400 | fresh |
| eternalai_ask_first | latency | 401 | fresh |
| eternalai_autopilot | latency | 401 | fresh |
| eternalai_ask_first | error_spike | 402 | fresh |
| eternalai_autopilot | error_spike | 402 | fresh |
| eternalai_ask_first | memory_leak | 403 | fresh |
| eternalai_autopilot | memory_leak | 403 | fresh |
| eternalai_ask_first | disk_fill | 404 | fresh |
| eternalai_autopilot | disk_fill | 404 | fresh |
| eternalai_ask_first | bad_deploy | 405 | fresh |
| eternalai_autopilot | bad_deploy | 405 | fresh |
| eternalai_autopilot | cpu_burn | 406 | fresh |
| eternalai_ask_first | crash | 410 | fresh |
| eternalai_autopilot | crash | 410 | fresh |
| eternalai_ask_first | latency | 411 | fresh |
| eternalai_autopilot | latency | 411 | fresh |
| eternalai_ask_first | error_spike | 412 | fresh |
| eternalai_autopilot | error_spike | 412 | fresh |
| eternalai_ask_first | memory_leak | 413 | fresh |
| eternalai_autopilot | memory_leak | 413 | fresh |
| eternalai_ask_first | disk_fill | 414 | fresh |
| eternalai_autopilot | disk_fill | 414 | fresh |
| eternalai_ask_first | bad_deploy | 415 | fresh |
| eternalai_autopilot | bad_deploy | 415 | fresh |
| eternalai_autopilot | cpu_burn | 416 | fresh |
| eternalai_ask_first | crash | 420 | fresh |
| eternalai_autopilot | crash | 420 | fresh |
| eternalai_ask_first | latency | 421 | fresh |
| eternalai_autopilot | latency | 421 | fresh |
| eternalai_ask_first | memory_leak | 423 | fresh |
| eternalai_autopilot | memory_leak | 423 | fresh |
| eternalai_ask_first | disk_fill | 424 | fresh |
| eternalai_autopilot | disk_fill | 424 | fresh |
| eternalai_autopilot | cpu_burn | 426 | fresh |
