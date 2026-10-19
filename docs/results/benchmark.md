# Held-out benchmark results

Rendered by `scripts/render_results.py` from the raw rows. Method and rules: `docs/EVALUATION_PLAN.md` (including Amendment 1). Cells with n = 5 are not compared for significance; intervals are bootstrap 95% over runs and are shown only for pooled metrics.

**How to read this document**

1. The **failed-request %** (section 2) is the independent measure: the evaluator reads it from the load generator, not from the system under test.
2. **Recovery is self-reported.** It comes from the system's own synthetic-checkout verification. It is never independently verified in v1; no raw probe logs exist. The consistency check in section 2 compares claimed recoveries with the no-action arm for the same seed.
3. **LLM path.** The benchmark brains were configured without LLM keys (by construction), so reports are expected to be template reports. The report provider is not recorded in the rows (design limitation, class c); section 1 counts incident timelines that contain a `report by <provider>` line, which the engine writes only for a non-template provider.


## 1. Run accounting

- rows in the raw file: 225; distinct (arm, scenario, seed) runs: 225 of 225 planned; duplicate rows: 0
- cells not at 5 runs: none
- system commit recorded in rows: {'eternalai_ask_first': ['3b29de5'], 'eternalai_autopilot': ['245d3e7'], 'no_action': ['3b29de5'], 'prototype_rules': ['3b29de5'], 'threshold_restart': ['3b29de5']}
- runs whose recorded incident timelines contain a `report by <provider>` line (non-template report): 0 of 225. Zero is consistent with template-only reports but is not a direct record; the provider is not stored per row.
- no run was dropped: every row enters every table below. Rows are never filtered.
- harness failures recorded: none listed in the failures file

## 1b. Headline comparison, all arms side by side

| arm                 |   failed-request % (mean, 30 supported runs) | self-reported recovery   | seconds to self-reported recovery (mean, recovered runs)   | healthy runs with a false alert   |   harmful interventions on healthy runs |   harmful interventions, all runs |
|:--------------------|---------------------------------------------:|:-------------------------|:-----------------------------------------------------------|:----------------------------------|----------------------------------------:|----------------------------------:|
| no_action           |                                        32.17 | 0/30                     | -                                                          | 0/10                              |                                       0 |                                 0 |
| threshold_restart   |                                        26.6  | 12/30                    | 68.2                                                       | 5/10                              |                                       0 |                                 5 |
| prototype_rules     |                                        26.29 | 9/30                     | 69.4                                                       | 8/10                              |                                       0 |                                 4 |
| eternalai_ask_first |                                        31.99 | 0/30                     | -                                                          | 0/10                              |                                       0 |                                 0 |
| eternalai_autopilot |                                        18.39 | 27/30                    | 50.0                                                       | 8/10                              |                                       4 |                                 4 |

Per supported scenario (5 runs per cell): self-reported recovery k/5, mean failed-request %, mean seconds to self-reported recovery.

| scenario    | no_action     | threshold_restart   | prototype_rules   | eternalai_ask_first   | eternalai_autopilot   |
|:------------|:--------------|:--------------------|:------------------|:----------------------|:----------------------|
| crash       | 0/5; 71.8%; - | 4/5; 49.4%; 65s     | 3/5; 50.3%; 71s   | 0/5; 70.5%; -         | 2/5; 45.9%; 40s       |
| latency     | 0/5; 0.0%; -  | 4/5; 4.0%; 71s      | 0/5; 1.0%; -      | 0/5; 0.0%; -          | 5/5; 8.1%; 55s        |
| error_spike | 0/5; 51.5%; - | 4/5; 38.4%; 69s     | 1/5; 50.0%; 71s   | 0/5; 52.0%; -         | 5/5; 25.2%; 48s       |
| memory_leak | 0/5; 0.4%; -  | 0/5; 0.1%; -        | 1/5; 0.4%; 62s    | 0/5; 0.0%; -          | 5/5; 11.2%; 49s       |
| disk_fill   | 0/5; 35.9%; - | 0/5; 33.9%; -       | 2/5; 28.8%; 79s   | 0/5; 35.1%; -         | 5/5; 0.0%; 39s        |
| bad_deploy  | 0/5; 33.5%; - | 0/5; 33.8%; -       | 2/5; 27.4%; 60s   | 0/5; 34.3%; -         | 5/5; 20.0%; 64s       |

## 2. The independent measure first: failed-request %

Computed by the evaluator from the load generator's counters between injection and the end of the observation window. It does not depend on what the system under test reports.


### Failed-request %, per cell (all scenarios)

All raw values in seed order (repetition 0..4), then mean and min to max. `-` = not defined for that run.

| scenario | arm | values | mean | min to max | n |
|---|---|---|---|---|---|
| crash | no_action | 27.61 100.00 31.18 100.00 100.00 | 71.76 | 27.61 to 100.00 | 5 |
| crash | threshold_restart | 16.17 58.08 19.25 53.59 100.00 | 49.42 | 16.17 to 100.00 | 5 |
| crash | prototype_rules | 20.04 52.51 29.35 49.41 100.00 | 50.26 | 20.04 to 100.00 | 5 |
| crash | eternalai_ask_first | 23.47 100.00 28.95 100.00 100.00 | 70.48 | 23.47 to 100.00 | 5 |
| crash | eternalai_autopilot | 26.13 36.33 29.32 100.00 37.72 | 45.90 | 26.13 to 100.00 | 5 |
| latency | no_action | 0.00 0.00 0.00 0.00 0.00 | 0.00 | 0.00 to 0.00 | 5 |
| latency | threshold_restart | 3.61 1.36 10.96 4.24 0.00 | 4.03 | 0.00 to 10.96 | 5 |
| latency | prototype_rules | 2.46 0.00 0.00 2.30 0.00 | 0.95 | 0.00 to 2.46 | 5 |
| latency | eternalai_ask_first | 0.00 0.00 0.00 0.00 0.00 | 0.00 | 0.00 to 0.00 | 5 |
| latency | eternalai_autopilot | 3.66 3.88 10.89 5.59 16.50 | 8.10 | 3.66 to 16.50 | 5 |
| error_spike | no_action | 13.70 67.44 21.72 71.16 83.56 | 51.52 | 13.70 to 83.56 | 5 |
| error_spike | threshold_restart | 8.86 38.71 13.20 44.25 86.74 | 38.35 | 8.86 to 86.74 | 5 |
| error_spike | prototype_rules | 8.39 66.44 23.60 70.66 80.82 | 49.98 | 8.39 to 80.82 | 5 |
| error_spike | eternalai_ask_first | 12.72 71.56 27.16 65.98 82.77 | 52.04 | 12.72 to 82.77 | 5 |
| error_spike | eternalai_autopilot | 6.56 36.47 10.00 32.84 40.06 | 25.19 | 6.56 to 40.06 | 5 |
| memory_leak | no_action | 1.84 0.00 0.00 0.00 0.00 | 0.37 | 0.00 to 1.84 | 5 |
| memory_leak | threshold_restart | 0.45 0.00 0.00 0.00 0.13 | 0.12 | 0.00 to 0.45 | 5 |
| memory_leak | prototype_rules | 1.99 0.00 0.00 0.00 0.00 | 0.40 | 0.00 to 1.99 | 5 |
| memory_leak | eternalai_ask_first | 0.15 0.00 0.00 0.00 0.00 | 0.03 | 0.00 to 0.15 | 5 |
| memory_leak | eternalai_autopilot | 13.73 15.19 10.61 14.02 2.33 | 11.18 | 2.33 to 15.19 | 5 |
| disk_fill | no_action | 0.00 0.00 22.10 78.31 78.93 | 35.87 | 0.00 to 78.93 | 5 |
| disk_fill | threshold_restart | 0.00 0.00 20.87 71.66 76.86 | 33.88 | 0.00 to 76.86 | 5 |
| disk_fill | prototype_rules | 6.29 1.57 19.15 77.29 39.76 | 28.81 | 1.57 to 77.29 | 5 |
| disk_fill | eternalai_ask_first | 0.00 0.00 21.20 77.25 76.87 | 35.06 | 0.00 to 77.25 | 5 |
| disk_fill | eternalai_autopilot | 0.00 0.00 0.00 0.00 0.00 | 0.00 | 0.00 to 0.00 | 5 |
| bad_deploy | no_action | 18.89 23.84 22.16 23.02 79.64 | 33.51 | 18.89 to 79.64 | 5 |
| bad_deploy | threshold_restart | 21.81 22.57 19.39 24.12 81.04 | 33.79 | 19.39 to 81.04 | 5 |
| bad_deploy | prototype_rules | 27.03 7.85 8.96 12.28 80.63 | 27.35 | 7.85 to 80.63 | 5 |
| bad_deploy | eternalai_ask_first | 24.67 23.20 21.48 23.22 78.95 | 34.30 | 21.48 to 78.95 | 5 |
| bad_deploy | eternalai_autopilot | 12.33 13.99 15.38 15.72 42.42 | 19.97 | 12.33 to 42.42 | 5 |
| cpu_burn | no_action | 96.74 0.00 97.76 90.15 28.37 | 62.60 | 0.00 to 97.76 | 5 |
| cpu_burn | threshold_restart | 50.93 1.55 50.61 56.18 17.90 | 35.43 | 1.55 to 56.18 | 5 |
| cpu_burn | prototype_rules | 71.38 2.09 99.59 58.93 25.00 | 51.40 | 2.09 to 99.59 | 5 |
| cpu_burn | eternalai_ask_first | 72.08 0.00 99.39 59.45 30.20 | 52.22 | 0.00 to 99.39 | 5 |
| cpu_burn | eternalai_autopilot | 45.45 0.00 48.89 74.80 18.40 | 37.51 | 0.00 to 74.80 | 5 |
| traffic_surge | no_action | 0.00 0.00 0.00 0.00 0.00 | 0.00 | 0.00 to 0.00 | 5 |
| traffic_surge | threshold_restart | 0.00 0.00 0.00 0.00 0.00 | 0.00 | 0.00 to 0.00 | 5 |
| traffic_surge | prototype_rules | 0.00 0.00 0.00 0.00 0.00 | 0.00 | 0.00 to 0.00 | 5 |
| traffic_surge | eternalai_ask_first | 0.00 0.00 0.00 0.00 0.00 | 0.00 | 0.00 to 0.00 | 5 |
| traffic_surge | eternalai_autopilot | 15.36 0.00 18.40 17.40 12.24 | 12.68 | 0.00 to 18.40 | 5 |
| good_deploy | no_action | 3.67 3.15 2.30 4.57 9.49 | 4.64 | 2.30 to 9.49 | 5 |
| good_deploy | threshold_restart | 3.42 3.89 1.49 2.82 13.92 | 5.11 | 1.49 to 13.92 | 5 |
| good_deploy | prototype_rules | 1.98 3.16 1.08 3.02 9.73 | 3.79 | 1.08 to 9.73 | 5 |
| good_deploy | eternalai_ask_first | 3.33 1.50 3.19 3.12 4.56 | 3.14 | 1.50 to 4.56 | 5 |
| good_deploy | eternalai_autopilot | 2.43 4.29 3.33 2.10 12.93 | 5.02 | 2.10 to 12.93 | 5 |

### Consistency check of self-reported recovery against the no-action arm

A claimed recovery should come with a failed-request % no higher than the `no_action` arm's value for the same seed. Claimed recoveries compared: 48. Violations, one per line:

- eternalai_autopilot / latency / seed 101: claimed recovered with 3.66% failed vs 0.00% with no action
- eternalai_autopilot / memory_leak / seed 103: claimed recovered with 13.73% failed vs 1.84% with no action
- eternalai_autopilot / latency / seed 111: claimed recovered with 3.88% failed vs 0.00% with no action
- eternalai_autopilot / memory_leak / seed 113: claimed recovered with 15.19% failed vs 0.00% with no action
- eternalai_autopilot / memory_leak / seed 123: claimed recovered with 10.61% failed vs 0.00% with no action
- eternalai_autopilot / latency / seed 121: claimed recovered with 10.89% failed vs 0.00% with no action
- eternalai_autopilot / latency / seed 131: claimed recovered with 5.59% failed vs 0.00% with no action
- eternalai_autopilot / memory_leak / seed 133: claimed recovered with 14.02% failed vs 0.00% with no action
- eternalai_autopilot / latency / seed 141: claimed recovered with 16.50% failed vs 0.00% with no action
- eternalai_autopilot / memory_leak / seed 143: claimed recovered with 2.33% failed vs 0.00% with no action
- threshold_restart / latency / seed 101: claimed recovered with 3.61% failed vs 0.00% with no action
- threshold_restart / latency / seed 111: claimed recovered with 1.36% failed vs 0.00% with no action
- threshold_restart / latency / seed 121: claimed recovered with 10.96% failed vs 0.00% with no action
- threshold_restart / latency / seed 131: claimed recovered with 4.24% failed vs 0.00% with no action
- prototype_rules / disk_fill / seed 104: claimed recovered with 6.29% failed vs 0.00% with no action
- prototype_rules / memory_leak / seed 103: claimed recovered with 1.99% failed vs 1.84% with no action
- prototype_rules / disk_fill / seed 114: claimed recovered with 1.57% failed vs 0.00% with no action

## 3. Everything else per cell (reported by the system under test or derived from its incident log)


### Recovery, SELF-REPORTED by the system's own checkout verification (1 = recovered, 0 = not), supported fault scenarios

All raw values in seed order (repetition 0..4), then mean and min to max. `-` = not defined for that run.

| scenario | arm | values | mean | min to max | n |
|---|---|---|---|---|---|
| crash | no_action | 0 0 0 0 0 | 0.00 | 0 to 0 | 5 |
| crash | threshold_restart | 1 1 1 1 0 | 0.80 | 0 to 1 | 5 |
| crash | prototype_rules | 1 1 0 1 0 | 0.60 | 0 to 1 | 5 |
| crash | eternalai_ask_first | 0 0 0 0 0 | 0.00 | 0 to 0 | 5 |
| crash | eternalai_autopilot | 0 1 0 0 1 | 0.40 | 0 to 1 | 5 |
| latency | no_action | 0 0 0 0 0 | 0.00 | 0 to 0 | 5 |
| latency | threshold_restart | 1 1 1 1 0 | 0.80 | 0 to 1 | 5 |
| latency | prototype_rules | 0 0 0 0 0 | 0.00 | 0 to 0 | 5 |
| latency | eternalai_ask_first | 0 0 0 0 0 | 0.00 | 0 to 0 | 5 |
| latency | eternalai_autopilot | 1 1 1 1 1 | 1.00 | 1 to 1 | 5 |
| error_spike | no_action | 0 0 0 0 0 | 0.00 | 0 to 0 | 5 |
| error_spike | threshold_restart | 1 1 1 1 0 | 0.80 | 0 to 1 | 5 |
| error_spike | prototype_rules | 1 0 0 0 0 | 0.20 | 0 to 1 | 5 |
| error_spike | eternalai_ask_first | 0 0 0 0 0 | 0.00 | 0 to 0 | 5 |
| error_spike | eternalai_autopilot | 1 1 1 1 1 | 1.00 | 1 to 1 | 5 |
| memory_leak | no_action | 0 0 0 0 0 | 0.00 | 0 to 0 | 5 |
| memory_leak | threshold_restart | 0 0 0 0 0 | 0.00 | 0 to 0 | 5 |
| memory_leak | prototype_rules | 1 0 0 0 0 | 0.20 | 0 to 1 | 5 |
| memory_leak | eternalai_ask_first | 0 0 0 0 0 | 0.00 | 0 to 0 | 5 |
| memory_leak | eternalai_autopilot | 1 1 1 1 1 | 1.00 | 1 to 1 | 5 |
| disk_fill | no_action | 0 0 0 0 0 | 0.00 | 0 to 0 | 5 |
| disk_fill | threshold_restart | 0 0 0 0 0 | 0.00 | 0 to 0 | 5 |
| disk_fill | prototype_rules | 1 1 0 0 0 | 0.40 | 0 to 1 | 5 |
| disk_fill | eternalai_ask_first | 0 0 0 0 0 | 0.00 | 0 to 0 | 5 |
| disk_fill | eternalai_autopilot | 1 1 1 1 1 | 1.00 | 1 to 1 | 5 |
| bad_deploy | no_action | 0 0 0 0 0 | 0.00 | 0 to 0 | 5 |
| bad_deploy | threshold_restart | 0 0 0 0 0 | 0.00 | 0 to 0 | 5 |
| bad_deploy | prototype_rules | 0 0 1 1 0 | 0.40 | 0 to 1 | 5 |
| bad_deploy | eternalai_ask_first | 0 0 0 0 0 | 0.00 | 0 to 0 | 5 |
| bad_deploy | eternalai_autopilot | 1 1 1 1 1 | 1.00 | 1 to 1 | 5 |

### Seconds to self-reported recovery (recovered runs only)

All raw values in seed order (repetition 0..4), then mean and min to max. `-` = not defined for that run.

| scenario | arm | values | mean | min to max | n |
|---|---|---|---|---|---|
| crash | no_action | - - - - - | - | - | 5 |
| crash | threshold_restart | 64.8 66.2 65.1 63.8 - | 65.0 | 63.8 to 66.2 | 5 |
| crash | prototype_rules | 84.9 62.3 - 66.2 - | 71.1 | 62.3 to 84.9 | 5 |
| crash | eternalai_ask_first | - - - - - | - | - | 5 |
| crash | eternalai_autopilot | - 40.5 - - 38.9 | 39.7 | 38.9 to 40.5 | 5 |
| latency | no_action | - - - - - | - | - | 5 |
| latency | threshold_restart | 71.1 68.7 70.8 74.0 - | 71.2 | 68.7 to 74.0 | 5 |
| latency | prototype_rules | - - - - - | - | - | 5 |
| latency | eternalai_ask_first | - - - - - | - | - | 5 |
| latency | eternalai_autopilot | 55.7 52.9 51.3 55.1 57.6 | 54.5 | 51.3 to 57.6 | 5 |
| error_spike | no_action | - - - - - | - | - | 5 |
| error_spike | threshold_restart | 71.6 66.5 68.6 67.6 - | 68.6 | 66.5 to 71.6 | 5 |
| error_spike | prototype_rules | 70.7 - - - - | 70.7 | 70.7 to 70.7 | 5 |
| error_spike | eternalai_ask_first | - - - - - | - | - | 5 |
| error_spike | eternalai_autopilot | 46.8 48.3 44.4 51.0 48.6 | 47.8 | 44.4 to 51.0 | 5 |
| memory_leak | no_action | - - - - - | - | - | 5 |
| memory_leak | threshold_restart | - - - - - | - | - | 5 |
| memory_leak | prototype_rules | 61.9 - - - - | 61.9 | 61.9 to 61.9 | 5 |
| memory_leak | eternalai_ask_first | - - - - - | - | - | 5 |
| memory_leak | eternalai_autopilot | 47.2 46.6 54.6 48.5 46.8 | 48.7 | 46.6 to 54.6 | 5 |
| disk_fill | no_action | - - - - - | - | - | 5 |
| disk_fill | threshold_restart | - - - - - | - | - | 5 |
| disk_fill | prototype_rules | 82.0 76.2 - - - | 79.1 | 76.2 to 82.0 | 5 |
| disk_fill | eternalai_ask_first | - - - - - | - | - | 5 |
| disk_fill | eternalai_autopilot | 38.8 39.1 37.9 40.2 37.2 | 38.6 | 37.2 to 40.2 | 5 |
| bad_deploy | no_action | - - - - - | - | - | 5 |
| bad_deploy | threshold_restart | - - - - - | - | - | 5 |
| bad_deploy | prototype_rules | - - 55.6 64.7 - | 60.2 | 55.6 to 64.7 | 5 |
| bad_deploy | eternalai_ask_first | - - - - - | - | - | 5 |
| bad_deploy | eternalai_autopilot | 67.3 68.3 67.7 70.3 48.0 | 64.3 | 48.0 to 70.3 | 5 |

### Detection time, seconds (detected runs only)

All raw values in seed order (repetition 0..4), then mean and min to max. `-` = not defined for that run.

| scenario | arm | values | mean | min to max | n |
|---|---|---|---|---|---|
| crash | no_action | - - - - - | - | - | 5 |
| crash | threshold_restart | 9.6 8.9 9.8 8.5 10.3 | 9.4 | 8.5 to 10.3 | 5 |
| crash | prototype_rules | 29.6 6.9 36.2 10.8 11.2 | 18.9 | 6.9 to 36.2 | 5 |
| crash | eternalai_ask_first | 6.1 - - - - | 6.1 | 6.1 to 6.1 | 5 |
| crash | eternalai_autopilot | 5.3 4.9 4.8 6.2 4.5 | 5.1 | 4.5 to 6.2 | 5 |
| latency | no_action | - - - - - | - | - | 5 |
| latency | threshold_restart | 8.3 11.5 10.6 12.9 8.7 | 10.4 | 8.3 to 12.9 | 5 |
| latency | prototype_rules | 47.3 11.6 46.5 68.4 - | 43.5 | 11.6 to 68.4 | 5 |
| latency | eternalai_ask_first | - - - - - | - | - | 5 |
| latency | eternalai_autopilot | 13.7 15.0 13.4 12.5 13.7 | 13.7 | 12.5 to 15.0 | 5 |
| error_spike | no_action | - - - - - | - | - | 5 |
| error_spike | threshold_restart | 15.5 11.4 13.2 11.4 10.3 | 12.4 | 10.3 to 15.5 | 5 |
| error_spike | prototype_rules | 14.0 15.2 - 62.0 - | 30.4 | 14.0 to 62.0 | 5 |
| error_spike | eternalai_ask_first | - - - - - | - | - | 5 |
| error_spike | eternalai_autopilot | 10.7 11.8 7.5 10.5 10.0 | 10.1 | 7.5 to 11.8 | 5 |
| memory_leak | no_action | - - - - - | - | - | 5 |
| memory_leak | threshold_restart | - - - 101.9 - | 101.9 | 101.9 to 101.9 | 5 |
| memory_leak | prototype_rules | 5.2 20.7 4.4 - 16.7 | 11.8 | 4.4 to 20.7 | 5 |
| memory_leak | eternalai_ask_first | - - - - - | - | - | 5 |
| memory_leak | eternalai_autopilot | 8.4 9.8 13.5 9.7 10.2 | 10.3 | 8.4 to 13.5 | 5 |
| disk_fill | no_action | - - - - - | - | - | 5 |
| disk_fill | threshold_restart | - - 35.2 39.3 35.7 | 36.7 | 35.2 to 39.3 | 5 |
| disk_fill | prototype_rules | 25.9 20.0 29.9 64.7 4.8 | 29.1 | 4.8 to 64.7 | 5 |
| disk_fill | eternalai_ask_first | 7.5 - - - - | 7.5 | 7.5 to 7.5 | 5 |
| disk_fill | eternalai_autopilot | 7.7 8.1 6.2 8.7 6.3 | 7.4 | 6.2 to 8.7 | 5 |
| bad_deploy | no_action | - - - - - | - | - | 5 |
| bad_deploy | threshold_restart | 9.9 8.1 10.7 9.0 10.4 | 9.6 | 8.1 to 10.7 | 5 |
| bad_deploy | prototype_rules | - 59.6 -0.0 9.1 52.2 | 30.2 | -0.0 to 59.6 | 5 |
| bad_deploy | eternalai_ask_first | 31.1 - - - - | 31.1 | 31.1 to 31.1 | 5 |
| bad_deploy | eternalai_autopilot | 29.4 30.3 30.1 31.2 8.5 | 25.9 | 8.5 to 31.2 | 5 |
| cpu_burn | no_action | - - - - - | - | - | 5 |
| cpu_burn | threshold_restart | 7.9 14.7 10.5 8.7 7.2 | 9.8 | 7.2 to 14.7 | 5 |
| cpu_burn | prototype_rules | 15.2 2.2 19.3 12.2 3.6 | 10.5 | 2.2 to 19.3 | 5 |
| cpu_burn | eternalai_ask_first | - - - - - | - | - | 5 |
| cpu_burn | eternalai_autopilot | 6.2 7.8 12.7 5.9 13.8 | 9.3 | 5.9 to 13.8 | 5 |

### Root-cause top-1 (1 = injected service ranked first)

All raw values in seed order (repetition 0..4), then mean and min to max. `-` = not defined for that run.

| scenario | arm | values | mean | min to max | n |
|---|---|---|---|---|---|
| crash | no_action | 0 0 0 0 0 | 0.00 | 0 to 0 | 5 |
| crash | threshold_restart | 1 1 1 1 1 | 1.00 | 1 to 1 | 5 |
| crash | prototype_rules | 1 1 1 1 1 | 1.00 | 1 to 1 | 5 |
| crash | eternalai_ask_first | 0 0 0 0 0 | 0.00 | 0 to 0 | 5 |
| crash | eternalai_autopilot | 1 1 1 1 1 | 1.00 | 1 to 1 | 5 |
| latency | no_action | 0 0 0 0 0 | 0.00 | 0 to 0 | 5 |
| latency | threshold_restart | 1 1 1 0 1 | 0.80 | 0 to 1 | 5 |
| latency | prototype_rules | 1 0 1 0 0 | 0.40 | 0 to 1 | 5 |
| latency | eternalai_ask_first | 0 0 0 0 0 | 0.00 | 0 to 0 | 5 |
| latency | eternalai_autopilot | 1 1 1 1 1 | 1.00 | 1 to 1 | 5 |
| error_spike | no_action | 0 0 0 0 0 | 0.00 | 0 to 0 | 5 |
| error_spike | threshold_restart | 1 1 1 1 0 | 0.80 | 0 to 1 | 5 |
| error_spike | prototype_rules | 1 0 0 0 0 | 0.20 | 0 to 1 | 5 |
| error_spike | eternalai_ask_first | 0 0 0 0 0 | 0.00 | 0 to 0 | 5 |
| error_spike | eternalai_autopilot | 1 1 1 1 1 | 1.00 | 1 to 1 | 5 |
| memory_leak | no_action | 0 0 0 0 0 | 0.00 | 0 to 0 | 5 |
| memory_leak | threshold_restart | 0 0 0 0 0 | 0.00 | 0 to 0 | 5 |
| memory_leak | prototype_rules | 0 1 1 0 0 | 0.40 | 0 to 1 | 5 |
| memory_leak | eternalai_ask_first | 0 0 0 0 0 | 0.00 | 0 to 0 | 5 |
| memory_leak | eternalai_autopilot | 1 1 1 1 1 | 1.00 | 1 to 1 | 5 |
| disk_fill | no_action | 0 0 0 0 0 | 0.00 | 0 to 0 | 5 |
| disk_fill | threshold_restart | 0 0 1 0 0 | 0.20 | 0 to 1 | 5 |
| disk_fill | prototype_rules | 1 1 0 0 0 | 0.40 | 0 to 1 | 5 |
| disk_fill | eternalai_ask_first | 0 0 0 0 0 | 0.00 | 0 to 0 | 5 |
| disk_fill | eternalai_autopilot | 1 1 1 1 1 | 1.00 | 1 to 1 | 5 |
| bad_deploy | no_action | 0 0 0 0 0 | 0.00 | 0 to 0 | 5 |
| bad_deploy | threshold_restart | 1 1 1 1 1 | 1.00 | 1 to 1 | 5 |
| bad_deploy | prototype_rules | 0 0 1 1 1 | 0.60 | 0 to 1 | 5 |
| bad_deploy | eternalai_ask_first | 1 0 0 0 0 | 0.20 | 0 to 1 | 5 |
| bad_deploy | eternalai_autopilot | 1 1 1 1 1 | 1.00 | 1 to 1 | 5 |

### False alerts on healthy runs (incidents opened)

All raw values in seed order (repetition 0..4), then mean and min to max. `-` = not defined for that run.

| scenario | arm | values | mean | min to max | n |
|---|---|---|---|---|---|
| traffic_surge | no_action | 0 0 0 0 0 | 0 | 0 to 0 | 5 |
| traffic_surge | threshold_restart | 0 0 0 0 0 | 0 | 0 to 0 | 5 |
| traffic_surge | prototype_rules | 1 1 1 0 2 | 1 | 0 to 2 | 5 |
| traffic_surge | eternalai_ask_first | 0 0 0 0 0 | 0 | 0 to 0 | 5 |
| traffic_surge | eternalai_autopilot | 1 1 1 1 1 | 1 | 1 to 1 | 5 |
| good_deploy | no_action | 0 0 0 0 0 | 0 | 0 to 0 | 5 |
| good_deploy | threshold_restart | 1 1 1 1 1 | 1 | 1 to 1 | 5 |
| good_deploy | prototype_rules | 1 1 0 1 1 | 1 | 0 to 1 | 5 |
| good_deploy | eternalai_ask_first | 0 0 0 0 0 | 0 | 0 to 0 | 5 |
| good_deploy | eternalai_autopilot | 1 1 0 1 0 | 1 | 0 to 1 | 5 |

### Harmful interventions (executed actions on a service other than the target; any action in a healthy run)

All raw values in seed order (repetition 0..4), then mean and min to max. `-` = not defined for that run.

| scenario | arm | values | mean | min to max | n |
|---|---|---|---|---|---|
| crash | no_action | 0 0 0 0 0 | 0 | 0 to 0 | 5 |
| crash | threshold_restart | 0 0 0 0 0 | 0 | 0 to 0 | 5 |
| crash | prototype_rules | 0 0 0 0 0 | 0 | 0 to 0 | 5 |
| crash | eternalai_ask_first | 0 0 0 0 0 | 0 | 0 to 0 | 5 |
| crash | eternalai_autopilot | 0 0 0 0 0 | 0 | 0 to 0 | 5 |
| latency | no_action | 0 0 0 0 0 | 0 | 0 to 0 | 5 |
| latency | threshold_restart | 0 0 0 1 0 | 0 | 0 to 1 | 5 |
| latency | prototype_rules | 0 0 0 0 0 | 0 | 0 to 0 | 5 |
| latency | eternalai_ask_first | 0 0 0 0 0 | 0 | 0 to 0 | 5 |
| latency | eternalai_autopilot | 0 0 0 0 0 | 0 | 0 to 0 | 5 |
| error_spike | no_action | 0 0 0 0 0 | 0 | 0 to 0 | 5 |
| error_spike | threshold_restart | 0 0 0 0 1 | 0 | 0 to 1 | 5 |
| error_spike | prototype_rules | 0 1 0 0 0 | 0 | 0 to 1 | 5 |
| error_spike | eternalai_ask_first | 0 0 0 0 0 | 0 | 0 to 0 | 5 |
| error_spike | eternalai_autopilot | 0 0 0 0 0 | 0 | 0 to 0 | 5 |
| memory_leak | no_action | 0 0 0 0 0 | 0 | 0 to 0 | 5 |
| memory_leak | threshold_restart | 0 0 0 0 0 | 0 | 0 to 0 | 5 |
| memory_leak | prototype_rules | 1 0 0 0 0 | 0 | 0 to 1 | 5 |
| memory_leak | eternalai_ask_first | 0 0 0 0 0 | 0 | 0 to 0 | 5 |
| memory_leak | eternalai_autopilot | 0 0 0 0 0 | 0 | 0 to 0 | 5 |
| disk_fill | no_action | 0 0 0 0 0 | 0 | 0 to 0 | 5 |
| disk_fill | threshold_restart | 0 0 0 1 1 | 0 | 0 to 1 | 5 |
| disk_fill | prototype_rules | 0 0 0 0 0 | 0 | 0 to 0 | 5 |
| disk_fill | eternalai_ask_first | 0 0 0 0 0 | 0 | 0 to 0 | 5 |
| disk_fill | eternalai_autopilot | 0 0 0 0 0 | 0 | 0 to 0 | 5 |
| bad_deploy | no_action | 0 0 0 0 0 | 0 | 0 to 0 | 5 |
| bad_deploy | threshold_restart | 0 0 0 0 0 | 0 | 0 to 0 | 5 |
| bad_deploy | prototype_rules | 0 0 0 0 0 | 0 | 0 to 0 | 5 |
| bad_deploy | eternalai_ask_first | 0 0 0 0 0 | 0 | 0 to 0 | 5 |
| bad_deploy | eternalai_autopilot | 0 0 0 0 0 | 0 | 0 to 0 | 5 |
| cpu_burn | no_action | 0 0 0 0 0 | 0 | 0 to 0 | 5 |
| cpu_burn | threshold_restart | 0 1 0 0 0 | 0 | 0 to 1 | 5 |
| cpu_burn | prototype_rules | 0 1 1 0 0 | 0 | 0 to 1 | 5 |
| cpu_burn | eternalai_ask_first | 0 0 0 0 0 | 0 | 0 to 0 | 5 |
| cpu_burn | eternalai_autopilot | 0 0 0 0 0 | 0 | 0 to 0 | 5 |
| traffic_surge | no_action | 0 0 0 0 0 | 0 | 0 to 0 | 5 |
| traffic_surge | threshold_restart | 0 0 0 0 0 | 0 | 0 to 0 | 5 |
| traffic_surge | prototype_rules | 0 0 0 0 0 | 0 | 0 to 0 | 5 |
| traffic_surge | eternalai_ask_first | 0 0 0 0 0 | 0 | 0 to 0 | 5 |
| traffic_surge | eternalai_autopilot | 1 0 1 1 1 | 1 | 0 to 1 | 5 |
| good_deploy | no_action | 0 0 0 0 0 | 0 | 0 to 0 | 5 |
| good_deploy | threshold_restart | 0 0 0 0 0 | 0 | 0 to 0 | 5 |
| good_deploy | prototype_rules | 0 0 0 0 0 | 0 | 0 to 0 | 5 |
| good_deploy | eternalai_ask_first | 0 0 0 0 0 | 0 | 0 to 0 | 5 |
| good_deploy | eternalai_autopilot | 0 0 0 0 0 | 0 | 0 to 0 | 5 |

### Unseen fault: abstained correctly (1 = yes)

All raw values in seed order (repetition 0..4), then mean and min to max. `-` = not defined for that run.

| scenario | arm | values | mean | min to max | n |
|---|---|---|---|---|---|
| cpu_burn | no_action | 0 0 0 0 0 | 0.00 | 0 to 0 | 5 |
| cpu_burn | threshold_restart | 0 0 0 0 0 | 0.00 | 0 to 0 | 5 |
| cpu_burn | prototype_rules | 0 0 0 0 0 | 0.00 | 0 to 0 | 5 |
| cpu_burn | eternalai_ask_first | 0 0 0 0 0 | 0.00 | 0 to 0 | 5 |
| cpu_burn | eternalai_autopilot | 1 1 0 1 1 | 0.80 | 0 to 1 | 5 |

### Unseen fault: self-reported recovery (not expected from EternalAI by design)

All raw values in seed order (repetition 0..4), then mean and min to max. `-` = not defined for that run.

| scenario | arm | values | mean | min to max | n |
|---|---|---|---|---|---|
| cpu_burn | no_action | 0 0 0 0 0 | 0.00 | 0 to 0 | 5 |
| cpu_burn | threshold_restart | 1 1 1 1 1 | 1.00 | 1 to 1 | 5 |
| cpu_burn | prototype_rules | 0 1 0 1 0 | 0.40 | 0 to 1 | 5 |
| cpu_burn | eternalai_ask_first | 0 0 0 0 0 | 0.00 | 0 to 0 | 5 |
| cpu_burn | eternalai_autopilot | 0 0 1 0 0 | 0.20 | 0 to 1 | 5 |

## 4. Pooled metrics per arm (bootstrap 95% interval over runs)

| arm                 |   supported runs | failed requests % (supported runs; independent measure)   | recovery rate, self-reported   | seconds to self-reported recovery (recovered runs)   | detection time s (detected runs)   | root-cause top-1   | root-cause top-3   | healthy runs with a false alert   |   harmful interventions (all runs) | unseen fault: abstained correctly   | unseen fault: self-reported recovery   |
|:--------------------|-----------------:|:----------------------------------------------------------|:-------------------------------|:-----------------------------------------------------|:-----------------------------------|:-------------------|:-------------------|:----------------------------------|-----------------------------------:|:------------------------------------|:---------------------------------------|
| no_action           |               30 | 32.17 [19.51, 45.38] (n=30)                               | 0.0 [0.0, 0.0] (n=30)          | -                                                    | -                                  | -                  | -                  | 0/10                              |                                  0 | 0/5                                 | 0/5                                    |
| threshold_restart   |               30 | 26.60 [16.46, 38.06] (n=30)                               | 40.0 [23.3, 56.7] (n=30)       | 68.2 [66.6, 70.0] (n=12)                             | 17.5 [11.3, 26.5] (n=24)           | 19/30              | 23/30              | 5/10                              |                                  5 | 0/5                                 | 5/5                                    |
| prototype_rules     |               30 | 26.29 [15.79, 37.99] (n=30)                               | 30.0 [13.3, 46.7] (n=30)       | 69.4 [63.6, 75.6] (n=9)                              | 26.9 [19.3, 35.4] (n=25)           | 15/30              | 23/30              | 8/10                              |                                  4 | 0/5                                 | 2/5                                    |
| eternalai_ask_first |               30 | 31.99 [19.36, 45.31] (n=30)                               | 0.0 [0.0, 0.0] (n=30)          | -                                                    | 14.9 [6.1, 31.1] (n=3)             | 1/30               | 3/30               | 0/10                              |                                  0 | 0/5                                 | 0/5                                    |
| eternalai_autopilot |               30 | 18.39 [12.03, 26.18] (n=30)                               | 90.0 [80.0, 100.0] (n=30)      | 50.0 [46.6, 53.6] (n=27)                             | 12.1 [9.6, 15.0] (n=30)            | 30/30              | 30/30              | 8/10                              |                                  4 | 4/5                                 | 1/5                                    |

## 5. Pooled paired differences (same seeds; mean difference with bootstrap 95% interval over seeds)

Negative is better for times and failed-request %, positive is better for recovery. `interval excludes zero` is a statement about the interval only; it is not a significance test and the plan makes no claim from it for individual cells.

| arm                 | versus              | metric                             |   mean diff | 95% interval       |   paired seeds | interval excludes zero   | direction                   |
|:--------------------|:--------------------|:-----------------------------------|------------:|:-------------------|---------------:|:-------------------------|:----------------------------|
| eternalai_autopilot | no_action           | failed requests % (supported)      |     -13.781 | [-23.770, -4.545]  |             30 | True                     | favours eternalai_autopilot |
| eternalai_autopilot | no_action           | self-reported recovery (supported) |       0.9   | [0.767, 1.000]     |             30 | True                     | favours eternalai_autopilot |
| eternalai_autopilot | threshold_restart   | failed requests % (supported)      |      -8.208 | [-18.458, 0.537]   |             30 | False                    | favours eternalai_autopilot |
| eternalai_autopilot | threshold_restart   | self-reported recovery (supported) |       0.5   | [0.233, 0.733]     |             30 | True                     | favours eternalai_autopilot |
| eternalai_autopilot | threshold_restart   | seconds to self-reported recovery  |     -19.9   | [-22.412, -17.544] |              9 | True                     | favours eternalai_autopilot |
| eternalai_autopilot | threshold_restart   | detection time s                   |      -4.842 | [-15.223, 3.184]   |             24 | False                    | favours eternalai_autopilot |
| eternalai_autopilot | prototype_rules     | failed requests % (supported)      |      -7.904 | [-17.963, 0.971]   |             30 | False                    | favours eternalai_autopilot |
| eternalai_autopilot | prototype_rules     | self-reported recovery (supported) |       0.6   | [0.367, 0.800]     |             30 | True                     | favours eternalai_autopilot |
| eternalai_autopilot | prototype_rules     | seconds to self-reported recovery  |     -17.571 | [-31.715, -3.870]  |              7 | True                     | favours eternalai_autopilot |
| eternalai_autopilot | prototype_rules     | detection time s                   |     -15.224 | [-24.257, -6.432]  |             25 | True                     | favours eternalai_autopilot |
| eternalai_autopilot | eternalai_ask_first | failed requests % (supported)      |     -13.598 | [-23.636, -4.481]  |             30 | True                     | favours eternalai_autopilot |
| eternalai_autopilot | eternalai_ask_first | self-reported recovery (supported) |       0.9   | [0.767, 1.000]     |             30 | True                     | favours eternalai_autopilot |
| eternalai_autopilot | eternalai_ask_first | detection time s                   |      -0.767 | [-1.700, 0.200]    |              3 | False                    | favours eternalai_autopilot |
| eternalai_ask_first | no_action           | failed requests % (supported)      |      -0.183 | [-0.936, 0.627]    |             30 | False                    | favours eternalai_ask_first |
| eternalai_ask_first | no_action           | self-reported recovery (supported) |       0     | [0.000, 0.000]     |             30 | False                    | favours eternalai_ask_first |
| eternalai_ask_first | threshold_restart   | failed requests % (supported)      |       5.389 | [1.116, 10.427]    |             30 | True                     | favours threshold_restart   |
| eternalai_ask_first | threshold_restart   | self-reported recovery (supported) |      -0.4   | [-0.567, -0.233]   |             30 | True                     | favours threshold_restart   |
| eternalai_ask_first | prototype_rules     | failed requests % (supported)      |       5.694 | [1.181, 10.788]    |             30 | True                     | favours prototype_rules     |
| eternalai_ask_first | prototype_rules     | self-reported recovery (supported) |      -0.3   | [-0.467, -0.133]   |             30 | True                     | favours prototype_rules     |
| eternalai_ask_first | eternalai_autopilot | failed requests % (supported)      |      13.598 | [4.481, 23.636]    |             30 | True                     | favours eternalai_autopilot |
| eternalai_ask_first | eternalai_autopilot | self-reported recovery (supported) |      -0.9   | [-1.000, -0.767]   |             30 | True                     | favours eternalai_autopilot |
| eternalai_ask_first | eternalai_autopilot | detection time s                   |       0.767 | [-0.200, 1.700]    |              3 | False                    | favours eternalai_autopilot |

## 6. Metrics on which EternalAI is not ahead of an arm (pooled point estimates, plain list)

- self-reported recovery rate: eternalai_ask_first 0.00 versus no_action 0.00
- failed requests %: eternalai_ask_first 31.99 versus threshold_restart 26.60
- self-reported recovery rate: eternalai_ask_first 0.00 versus threshold_restart 0.40
- failed requests %: eternalai_ask_first 31.99 versus prototype_rules 26.29
- self-reported recovery rate: eternalai_ask_first 0.00 versus prototype_rules 0.30
- failed requests %: eternalai_ask_first 31.99 versus eternalai_autopilot 18.39
- self-reported recovery rate: eternalai_ask_first 0.00 versus eternalai_autopilot 0.90
- detection time s: eternalai_ask_first 14.90 versus eternalai_autopilot 12.09

## 7. Every non-recovery and its triage class

All supported-fault runs with `recovered` not true. Class from `docs/postmortems/triage.json`; a missing entry means unclassified (class a = harness artifact, b = system bug, c = design limitation).

| arm | scenario | seed | final status | class | evidence |
|---|---|---|---|---|---|
| eternalai_ask_first | bad_deploy | 105 | awaiting_approval | a | R1 harness artifact: an ask-first proposal stayed awaiting_approval because the harness token was refused by the brain (HTTP 503, placeholder token); amplifier (b): no expiry, so it blocked every later detection in the arm; final=awaiting_approval; actions=['rollback_release@payments:needs_approval']; incidents=[('awaiting_approval', 'bad_deploy', False)] |
| eternalai_ask_first | bad_deploy | 115 | undetected | a | R1 harness artifact: undetected because an earlier proposal stayed awaiting_approval (the harness token was refused by the brain) and, with no expiry (b), blocked new incidents; final=undetected; actions=[]; incidents=[] |
| eternalai_ask_first | bad_deploy | 125 | undetected | a | R1 harness artifact: undetected because an earlier proposal stayed awaiting_approval (the harness token was refused by the brain) and, with no expiry (b), blocked new incidents; final=undetected; actions=[]; incidents=[] |
| eternalai_ask_first | bad_deploy | 135 | undetected | a | R1 harness artifact: undetected because an earlier proposal stayed awaiting_approval (the harness token was refused by the brain) and, with no expiry (b), blocked new incidents; final=undetected; actions=[]; incidents=[] |
| eternalai_ask_first | bad_deploy | 145 | undetected | a | R1 harness artifact: undetected because an earlier proposal stayed awaiting_approval (the harness token was refused by the brain) and, with no expiry (b), blocked new incidents; final=undetected; actions=[]; incidents=[] |
| eternalai_ask_first | crash | 100 | escalated | c | R2 first incident abstained (insufficient_evidence) on a crash of orders; orders has 1 crash run in training; final=escalated; actions=[]; incidents=[('escalated', 'insufficient_evidence', True), ('open', 'pending', False)] |
| eternalai_ask_first | crash | 110 | undetected | a | R1 harness artifact: undetected because an earlier proposal stayed awaiting_approval (the harness token was refused by the brain) and, with no expiry (b), blocked new incidents; final=undetected; actions=[]; incidents=[] |
| eternalai_ask_first | crash | 120 | undetected | a | R1 harness artifact: undetected because an earlier proposal stayed awaiting_approval (the harness token was refused by the brain) and, with no expiry (b), blocked new incidents; final=undetected; actions=[]; incidents=[] |
| eternalai_ask_first | crash | 130 | undetected | a | R1 harness artifact: undetected because an earlier proposal stayed awaiting_approval (the harness token was refused by the brain) and, with no expiry (b), blocked new incidents; final=undetected; actions=[]; incidents=[] |
| eternalai_ask_first | crash | 140 | undetected | a | R1 harness artifact: undetected because an earlier proposal stayed awaiting_approval (the harness token was refused by the brain) and, with no expiry (b), blocked new incidents; final=undetected; actions=[]; incidents=[] |
| eternalai_ask_first | disk_fill | 104 | escalated | c | R6 the arm acted or escalated and the fault was not reported recovered; final=escalated; actions=[]; incidents=[('escalated', 'insufficient_evidence', True)] |
| eternalai_ask_first | disk_fill | 114 | undetected | a | R1 harness artifact: undetected because an earlier proposal stayed awaiting_approval (the harness token was refused by the brain) and, with no expiry (b), blocked new incidents; final=undetected; actions=[]; incidents=[] |
| eternalai_ask_first | disk_fill | 124 | undetected | a | R1 harness artifact: undetected because an earlier proposal stayed awaiting_approval (the harness token was refused by the brain) and, with no expiry (b), blocked new incidents; final=undetected; actions=[]; incidents=[] |
| eternalai_ask_first | disk_fill | 134 | undetected | a | R1 harness artifact: undetected because an earlier proposal stayed awaiting_approval (the harness token was refused by the brain) and, with no expiry (b), blocked new incidents; final=undetected; actions=[]; incidents=[] |
| eternalai_ask_first | disk_fill | 144 | undetected | a | R1 harness artifact: undetected because an earlier proposal stayed awaiting_approval (the harness token was refused by the brain) and, with no expiry (b), blocked new incidents; final=undetected; actions=[]; incidents=[] |
| eternalai_ask_first | error_spike | 102 | undetected | a | R1 harness artifact: undetected because an earlier proposal stayed awaiting_approval (the harness token was refused by the brain) and, with no expiry (b), blocked new incidents; final=undetected; actions=[]; incidents=[] |
| eternalai_ask_first | error_spike | 112 | undetected | a | R1 harness artifact: undetected because an earlier proposal stayed awaiting_approval (the harness token was refused by the brain) and, with no expiry (b), blocked new incidents; final=undetected; actions=[]; incidents=[] |
| eternalai_ask_first | error_spike | 122 | undetected | a | R1 harness artifact: undetected because an earlier proposal stayed awaiting_approval (the harness token was refused by the brain) and, with no expiry (b), blocked new incidents; final=undetected; actions=[]; incidents=[] |
| eternalai_ask_first | error_spike | 132 | undetected | a | R1 harness artifact: undetected because an earlier proposal stayed awaiting_approval (the harness token was refused by the brain) and, with no expiry (b), blocked new incidents; final=undetected; actions=[]; incidents=[] |
| eternalai_ask_first | error_spike | 142 | undetected | a | R1 harness artifact: undetected because an earlier proposal stayed awaiting_approval (the harness token was refused by the brain) and, with no expiry (b), blocked new incidents; final=undetected; actions=[]; incidents=[] |
| eternalai_ask_first | latency | 101 | undetected | a | R1 harness artifact: undetected because an earlier proposal stayed awaiting_approval (the harness token was refused by the brain) and, with no expiry (b), blocked new incidents; final=undetected; actions=[]; incidents=[] |
| eternalai_ask_first | latency | 111 | undetected | a | R1 harness artifact: undetected because an earlier proposal stayed awaiting_approval (the harness token was refused by the brain) and, with no expiry (b), blocked new incidents; final=undetected; actions=[]; incidents=[] |
| eternalai_ask_first | latency | 121 | undetected | a | R1 harness artifact: undetected because an earlier proposal stayed awaiting_approval (the harness token was refused by the brain) and, with no expiry (b), blocked new incidents; final=undetected; actions=[]; incidents=[] |
| eternalai_ask_first | latency | 131 | undetected | a | R1 harness artifact: undetected because an earlier proposal stayed awaiting_approval (the harness token was refused by the brain) and, with no expiry (b), blocked new incidents; final=undetected; actions=[]; incidents=[] |
| eternalai_ask_first | latency | 141 | undetected | a | R1 harness artifact: undetected because an earlier proposal stayed awaiting_approval (the harness token was refused by the brain) and, with no expiry (b), blocked new incidents; final=undetected; actions=[]; incidents=[] |
| eternalai_ask_first | memory_leak | 103 | undetected | a | R1 harness artifact: undetected because an earlier proposal stayed awaiting_approval (the harness token was refused by the brain) and, with no expiry (b), blocked new incidents; final=undetected; actions=[]; incidents=[] |
| eternalai_ask_first | memory_leak | 113 | undetected | a | R1 harness artifact: undetected because an earlier proposal stayed awaiting_approval (the harness token was refused by the brain) and, with no expiry (b), blocked new incidents; final=undetected; actions=[]; incidents=[] |
| eternalai_ask_first | memory_leak | 123 | undetected | a | R1 harness artifact: undetected because an earlier proposal stayed awaiting_approval (the harness token was refused by the brain) and, with no expiry (b), blocked new incidents; final=undetected; actions=[]; incidents=[] |
| eternalai_ask_first | memory_leak | 133 | undetected | a | R1 harness artifact: undetected because an earlier proposal stayed awaiting_approval (the harness token was refused by the brain) and, with no expiry (b), blocked new incidents; final=undetected; actions=[]; incidents=[] |
| eternalai_ask_first | memory_leak | 143 | undetected | a | R1 harness artifact: undetected because an earlier proposal stayed awaiting_approval (the harness token was refused by the brain) and, with no expiry (b), blocked new incidents; final=undetected; actions=[]; incidents=[] |
| eternalai_autopilot | crash | 100 | escalated | c | R2 first incident abstained (insufficient_evidence) on a crash of orders; orders has 1 crash run in training; final=escalated; actions=[]; incidents=[('escalated', 'insufficient_evidence', True), ('open', 'pending', False)] |
| eternalai_autopilot | crash | 120 | escalated | c | R2 first incident abstained (insufficient_evidence) on a crash of orders; orders has 1 crash run in training; final=escalated; actions=[]; incidents=[('escalated', 'insufficient_evidence', True), ('open', 'pending', False)] |
| eternalai_autopilot | crash | 130 | escalated | a | R3 restart blocked by a cooldown left by an action in an earlier run (the brain is not reset between runs); final=escalated; actions=['restart_service@inventory:blocked']; incidents=[('escalated', 'down', False)] |
| prototype_rules | bad_deploy | 105 | undetected | c | R5 no incident was ever opened by this arm's detector; final=undetected; actions=[]; incidents=[] |
| prototype_rules | bad_deploy | 115 | executing | a | R4 the run window ended while the incident was still 'executing'; final=executing; actions=['restart_service@orders:execute']; incidents=[('recovered', 'memory_leak', False), ('open', 'pending', False)] |
| prototype_rules | bad_deploy | 145 | escalated | a | R3 restart blocked by a cooldown left by an action in an earlier run (the brain is not reset between runs); final=escalated; actions=['rollback_release@inventory:blocked']; incidents=[('escalated', 'bad_deploy', False)] |
| prototype_rules | crash | 120 | escalated | a | R3 restart blocked by a cooldown left by an action in an earlier run (the brain is not reset between runs); final=escalated; actions=['restart_service@orders:blocked']; incidents=[('escalated', 'down', False)] |
| prototype_rules | crash | 140 | escalated | c | R6 the arm acted or escalated and the fault was not reported recovered; final=escalated; actions=['restart_service@web:blocked']; incidents=[('escalated', 'down', False), ('open', 'pending', False)] |
| prototype_rules | disk_fill | 124 | escalated | c | R6 the arm acted or escalated and the fault was not reported recovered; final=escalated; actions=['restart_service@web:blocked']; incidents=[('escalated', 'memory_leak', False)] |
| prototype_rules | disk_fill | 134 | escalated | c | R6 the arm acted or escalated and the fault was not reported recovered; final=escalated; actions=['restart_service@web:blocked']; incidents=[('escalated', 'memory_leak', False)] |
| prototype_rules | disk_fill | 144 | escalated | c | R6 the arm acted or escalated and the fault was not reported recovered; final=escalated; actions=['restart_service@web:blocked']; incidents=[('escalated', 'memory_leak', False)] |
| prototype_rules | error_spike | 112 | unresolved | c | R6 the arm acted or escalated and the fault was not reported recovered; final=unresolved; actions=['restart_service@orders:execute']; incidents=[('unresolved', 'memory_leak', False)] |
| prototype_rules | error_spike | 122 | undetected | c | R5 no incident was ever opened by this arm's detector; final=undetected; actions=[]; incidents=[] |
| prototype_rules | error_spike | 132 | escalated | c | R6 the arm acted or escalated and the fault was not reported recovered; final=escalated; actions=['restart_service@web:blocked']; incidents=[('escalated', 'memory_leak', False)] |
| prototype_rules | error_spike | 142 | undetected | c | R5 no incident was ever opened by this arm's detector; final=undetected; actions=[]; incidents=[] |
| prototype_rules | latency | 101 | verifying | a | R4 the run window ended while the incident was still 'verifying'; final=verifying; actions=['restart_service@orders:execute']; incidents=[('recovered', 'memory_leak', False), ('open', 'pending', False)] |
| prototype_rules | latency | 111 | escalated | c | R6 the arm acted or escalated and the fault was not reported recovered; final=escalated; actions=['restart_service@web:blocked']; incidents=[('escalated', 'memory_leak', False), ('open', 'pending', False)] |
| prototype_rules | latency | 121 | escalated | c | R6 the arm acted or escalated and the fault was not reported recovered; final=escalated; actions=['restart_service@web:blocked']; incidents=[('escalated', 'memory_leak', False)] |
| prototype_rules | latency | 131 | open | a | R4 the run window ended while the incident was still 'open'; final=open; actions=['restart_service@web:blocked']; incidents=[('escalated', 'memory_leak', False)] |
| prototype_rules | latency | 141 | undetected | c | R5 no incident was ever opened by this arm's detector; final=undetected; actions=[]; incidents=[] |
| prototype_rules | memory_leak | 113 | escalated | c | R6 the arm acted or escalated and the fault was not reported recovered; final=escalated; actions=['restart_service@web:blocked']; incidents=[('escalated', 'memory_leak', False)] |
| prototype_rules | memory_leak | 123 | escalated | c | R6 the arm acted or escalated and the fault was not reported recovered; final=escalated; actions=['restart_service@web:blocked']; incidents=[('escalated', 'memory_leak', False)] |
| prototype_rules | memory_leak | 133 | undetected | c | R5 no incident was ever opened by this arm's detector; final=undetected; actions=[]; incidents=[] |
| prototype_rules | memory_leak | 143 | escalated | c | R6 the arm acted or escalated and the fault was not reported recovered; final=escalated; actions=['restart_service@web:blocked']; incidents=[('escalated', 'memory_leak', False)] |
| threshold_restart | bad_deploy | 105 | unresolved | c | R6 the arm acted or escalated and the fault was not reported recovered; final=unresolved; actions=['restart_service@payments:execute']; incidents=[('unresolved', 'insufficient_evidence', False)] |
| threshold_restart | bad_deploy | 115 | unresolved | c | R6 the arm acted or escalated and the fault was not reported recovered; final=unresolved; actions=['restart_service@payments:execute']; incidents=[('unresolved', 'insufficient_evidence', False)] |
| threshold_restart | bad_deploy | 125 | unresolved | c | R6 the arm acted or escalated and the fault was not reported recovered; final=unresolved; actions=['restart_service@orders:execute']; incidents=[('unresolved', 'insufficient_evidence', False)] |
| threshold_restart | bad_deploy | 135 | escalated | c | R6 the arm acted or escalated and the fault was not reported recovered; final=escalated; actions=['restart_service@payments:blocked']; incidents=[('escalated', 'insufficient_evidence', False)] |
| threshold_restart | bad_deploy | 145 | unresolved | c | R6 the arm acted or escalated and the fault was not reported recovered; final=unresolved; actions=['restart_service@inventory:execute']; incidents=[('unresolved', 'insufficient_evidence', False)] |
| threshold_restart | crash | 140 | escalated | c | R6 the arm acted or escalated and the fault was not reported recovered; final=escalated; actions=['restart_service@web:blocked']; incidents=[('escalated', 'insufficient_evidence', False)] |
| threshold_restart | disk_fill | 104 | undetected | c | R5 no incident was ever opened by this arm's detector; final=undetected; actions=[]; incidents=[('open', 'pending', False)] |
| threshold_restart | disk_fill | 114 | undetected | c | R5 no incident was ever opened by this arm's detector; final=undetected; actions=[]; incidents=[] |
| threshold_restart | disk_fill | 124 | escalated | c | R6 the arm acted or escalated and the fault was not reported recovered; final=escalated; actions=['restart_service@payments:blocked']; incidents=[('escalated', 'insufficient_evidence', False)] |
| threshold_restart | disk_fill | 134 | unresolved | c | R6 the arm acted or escalated and the fault was not reported recovered; final=unresolved; actions=['restart_service@web:execute']; incidents=[('unresolved', 'insufficient_evidence', False)] |
| threshold_restart | disk_fill | 144 | unresolved | c | R6 the arm acted or escalated and the fault was not reported recovered; final=unresolved; actions=['restart_service@web:execute']; incidents=[('unresolved', 'insufficient_evidence', False)] |
| threshold_restart | error_spike | 142 | unresolved | c | R6 the arm acted or escalated and the fault was not reported recovered; final=unresolved; actions=['restart_service@orders:execute']; incidents=[('unresolved', 'insufficient_evidence', False)] |
| threshold_restart | latency | 141 | escalated | c | R6 the arm acted or escalated and the fault was not reported recovered; final=escalated; actions=['restart_service@web:blocked']; incidents=[('escalated', 'insufficient_evidence', False)] |
| threshold_restart | memory_leak | 103 | undetected | c | R5 no incident was ever opened by this arm's detector; final=undetected; actions=[]; incidents=[] |
| threshold_restart | memory_leak | 113 | undetected | c | R5 no incident was ever opened by this arm's detector; final=undetected; actions=[]; incidents=[] |
| threshold_restart | memory_leak | 123 | undetected | c | R5 no incident was ever opened by this arm's detector; final=undetected; actions=[]; incidents=[] |
| threshold_restart | memory_leak | 133 | open | a | R4 the run window ended while the incident was still 'open'; final=open; actions=[]; incidents=[('escalated', 'insufficient_evidence', False)] |
| threshold_restart | memory_leak | 143 | undetected | c | R5 no incident was ever opened by this arm's detector; final=undetected; actions=[]; incidents=[] |

- non-recoveries: 72; classified: 72
