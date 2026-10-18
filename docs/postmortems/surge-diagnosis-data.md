# Surge diagnosis, data side (offline, in-sample for models-v1)

## 1. Traffic variation in the training data

| run                | target   | params                       | web rps pre->surge   | orders rps pre->surge   | inventory rps pre->surge   | payments rps pre->surge   |
|:-------------------|:---------|:-----------------------------|:---------------------|:------------------------|:---------------------------|:--------------------------|
| traffic_surge_1007 | web      | {'extra_rps_per_thread': 25} | 6.1->78.8            | 1.9->1.6                | 8.1->80.5                  | 1.9->1.6                  |
| traffic_surge_1107 | web      | {'extra_rps_per_thread': 25} | 6.2->80.6            | 1.5->2.1                | 7.6->82.8                  | 1.5->2.1                  |
| traffic_surge_1207 | web      | {'extra_rps_per_thread': 25} | 6.2->79.7            | 1.7->1.8                | 7.9->81.6                  | 1.7->1.8                  |
| traffic_surge_1307 | web      | {'extra_rps_per_thread': 25} | 5.6->80.4            | 1.6->1.3                | 7.0->81.6                  | 1.6->1.4                  |
| traffic_surge_1407 | web      | {'extra_rps_per_thread': 25} | 6.6->81.4            | 2.1->1.7                | 8.7->83.1                  | 2.1->1.7                  |
| traffic_surge_1507 | web      | {'extra_rps_per_thread': 25} | 5.9->77.3            | 1.6->1.3                | 7.5->78.6                  | 1.6->1.3                  |
| traffic_surge_1607 | web      | {'extra_rps_per_thread': 25} | 6.7->78.5            | 2.0->1.8                | 8.6->80.4                  | 2.0->1.8                  |
| traffic_surge_1707 | web      | {'extra_rps_per_thread': 25} | 6.0->79.1            | 1.9->1.9                | 7.7->81.0                  | 1.9->1.9                  |

Distinct surge parameter sets in training: ["{'extra_rps_per_thread': 25}"]; targets: ['web']; runs: 8. The evaluator's surge lasts 40 s (`evaluator/scenarios.py`).

## 2. Frozen detector and classifier on the training surge windows (5-40 s after injection)

| service   |   windows | detector flagged   | classifier labels   | limit exceedances (feature: windows)   |
|:----------|----------:|:-------------------|:--------------------|:---------------------------------------|
| inventory |       144 | 0 (0%)             | {'healthy': 144}    | {}                                     |
| orders    |       144 | 0 (0%)             | {'healthy': 144}    | {}                                     |
| payments  |       144 | 0 (0%)             | {'healthy': 144}    | {}                                     |
| web       |       144 | 0 (0%)             | {'healthy': 144}    | {}                                     |

## 3. Memory relative to the healthy baseline, before and during the surge (median over training surge runs)

| service   |   median MB before |   median MB during surge |   runs |
|:----------|-------------------:|-------------------------:|-------:|
| web       |               68.8 |                     69.8 |      8 |
| orders    |               69.9 |                     69.9 |      8 |
| inventory |               65   |                     67.4 |      8 |
| payments  |               64.4 |                     64.4 |      8 |

## 5. Memory-related features on surge windows versus the learned healthy limits

| service   | feature                 |   surge windows: median |    p95 |    max |   learned limit (hi) |
|:----------|:------------------------|------------------------:|-------:|-------:|---------------------:|
| inventory | mem_slope_share_per_min |                  0.0035 | 0.0296 | 0.0355 |               0.062  |
| inventory | mem_share               |                  0.2505 | 0.2516 | 0.2517 |               0.2603 |
| orders    | mem_slope_share_per_min |                  0      | 0.0018 | 0.0034 |               0.0254 |
| orders    | mem_share               |                  0.2603 | 0.2667 | 0.2667 |               0.2738 |
| payments  | mem_slope_share_per_min |                  0      | 0.0022 | 0.0033 |               0.0143 |
| payments  | mem_share               |                  0.2399 | 0.2438 | 0.2439 |               0.2492 |
| web       | mem_slope_share_per_min |                  0.0024 | 0.0259 | 0.0349 |               0.0556 |
| web       | mem_share               |                  0.26   | 0.2628 | 0.2634 |               0.2794 |

The rule baseline (`eternalai/classify.py::rule_diagnose`, used by the prototype_rules arm) says `memory_leak` when `mem_share > 0.8` or `mem_slope_share_per_min > 0.05`.

## 6. Does a service's healthy memory drift with uptime/run order? (pre-injection median memory per training run, in seed order)

| service   |   runs |   pre-injection MB min |   median |   max |   MB per 100 seeds (linear fit) |   learned mem_share limit as MB (of 256 MiB) |
|:----------|-------:|-----------------------:|---------:|------:|--------------------------------:|---------------------------------------------:|
| inventory |     71 |                   64.5 |     65.3 |  67.2 |                           -0.01 |                                         69.9 |
| web       |     71 |                   65.3 |     66.8 |  71.1 |                            0.02 |                                         75   |

The learned `mem_share` limit sits a few MB above the largest healthy memory seen in training. A service whose healthy memory is a little higher in a longer-lived container (or that allocates a few MB more under load) is outside the learned healthy range. This is a hypothesis about the live behaviour; the benchmark rows hold no memory series to test it.

## 4. Model inputs: traffic-normalised or not

Classifier inputs (44): cpu_per_req_ratio, cpu_per_req_ratio_obs, cpu_per_req_z, cpu_per_req_z_obs, cpu_ratio, cpu_ratio_obs, cpu_z, cpu_z_obs, dep_fail_rate, dep_fail_rate_obs, deploys_3m, deploys_3m_obs, error_log_rate, error_log_rate_obs, error_ratio, error_ratio_delta, error_ratio_delta_obs, error_ratio_obs, error_ratio_z, error_ratio_z_obs, lat_ratio, lat_ratio_obs, lat_z, lat_z_obs, mem_ratio, mem_ratio_obs, mem_share, mem_share_obs, mem_slope_share_per_min, mem_slope_share_per_min_obs, mem_z, mem_z_obs, restarts_in_window, restarts_in_window_obs, rps_ratio, rps_ratio_obs, rps_z, rps_z_obs, scratch_mb, scratch_mb_obs, scratch_slope_mb_per_min, scratch_slope_mb_per_min_obs, up_frac, up_frac_obs.

Names containing `per_req` (explicitly divided by request rate): ['cpu_per_req_ratio', 'cpu_per_req_ratio_obs', 'cpu_per_req_z', 'cpu_per_req_z_obs']. Everything else is a ratio or z-score against the service's own healthy baseline, which does not remove a change in request rate; `rps_ratio` and `rps_z` are themselves inputs, so the models can see the surge. Memory features (`mem_*`) are not normalised for traffic.
