# Forecast check (live, watch-only)

Design, definitions and pass criteria: `docs/FORECAST_CHECK.md`, fixed before the runs. Brain in watch-only mode, non-benchmark seeds, template LLM path not involved. Counts over the runs actually made; with 5 runs per scenario no rate or interval is claimed.

## Criteria

| criterion | result | detail |
|---|---|---|
| memory_leak: warning issued before the limit in at least 4 of 5 runs | PASS | 5 of 5 runs |
| memory_leak: median lead time at least 30 s | FAIL | median 18.3 s over 5 warned runs; leads [8.1, 9.8, 18.3, 19.1, 34.5] |
| memory_leak: warnings on the wrong service | PASS | 0 in 5 runs |
| disk_fill: warning issued before the limit in at least 4 of 5 runs | PASS | 5 of 5 runs |
| disk_fill: median lead time at least 30 s | PASS | median 86.4 s over 5 warned runs; leads [73.7, 75.5, 86.4, 86.5, 87.0] |
| disk_fill: warnings on the wrong service | PASS | 0 in 5 runs |
| traffic_surge: warnings (any forecast warning) | PASS | 0 warnings in 5 healthy runs |
| good_deploy: warnings (any forecast warning) | PASS | 0 warnings in 5 healthy runs |
| watch-only: executed actions in every run | PASS | 0 executed actions in 20 runs |
| watch-only: an incident opened in each leak/disk run | PASS | 10 of 10 runs |

## Per run

| scenario      |   seed | target    |   incidents |   predicted incidents |   warnings | warned   | warning service   | wrong service   |   t_warn_after_inject_s |   t_limit_after_inject_s | limit_reached   |   lead_s | stated_window_s   | actual_inside_window   |   forecast_evidence_on_reactive |   executed_actions |
|:--------------|-------:|:----------|------------:|----------------------:|-----------:|:---------|:------------------|:----------------|------------------------:|-------------------------:|:----------------|---------:|:------------------|:-----------------------|--------------------------------:|-------------------:|
| disk_fill     |   3000 | orders    |           3 |                     2 |          3 | True     | orders            | False           |                    76.3 |                      150 | True            |     73.7 | (84, 111)         | False                  |                               1 |                  0 |
| disk_fill     |   3001 | payments  |           3 |                     2 |          3 | True     | payments          | False           |                   113.5 |                      200 | True            |     86.5 | (88, 88)          | False                  |                               0 |                  0 |
| disk_fill     |   3002 | orders    |           3 |                     1 |          1 | True     | orders            | False           |                   213   |                      300 | True            |     87   | (88, 88)          | False                  |                               3 |                  0 |
| disk_fill     |   3003 | inventory |           3 |                     2 |          3 | True     | inventory         | False           |                    74.5 |                      150 | True            |     75.5 | (84, 111)         | False                  |                               1 |                  0 |
| disk_fill     |   3004 | inventory |           3 |                     2 |          3 | True     | inventory         | False           |                   113.6 |                      200 | True            |     86.4 | (88, 88)          | False                  |                               1 |                  0 |
| good_deploy   |   3000 | orders    |           1 |                     0 |          0 | False    | nan               | False           |                   nan   |                      nan | False           |    nan   |                   |                        |                               1 |                  0 |
| good_deploy   |   3001 | payments  |           0 |                     0 |          0 | False    | nan               | False           |                   nan   |                      nan | False           |    nan   |                   |                        |                               0 |                  0 |
| good_deploy   |   3002 | orders    |           0 |                     0 |          0 | False    | nan               | False           |                   nan   |                      nan | False           |    nan   |                   |                        |                               0 |                  0 |
| good_deploy   |   3003 | inventory |           0 |                     0 |          0 | False    | nan               | False           |                   nan   |                      nan | False           |    nan   |                   |                        |                               0 |                  0 |
| good_deploy   |   3004 | inventory |           0 |                     0 |          0 | False    | nan               | False           |                   nan   |                      nan | False           |    nan   |                   |                        |                               0 |                  0 |
| memory_leak   |   3000 | orders    |           2 |                     1 |          2 | True     | orders            | False           |                    37.9 |                       46 | True            |      8.1 | (69, 4027)        | False                  |                               1 |                  0 |
| memory_leak   |   3001 | payments  |           1 |                     0 |          1 | True     | payments          | False           |                    42.9 |                       62 | True            |     19.1 | (83, 347)         | False                  |                               0 |                  0 |
| memory_leak   |   3002 | orders    |           2 |                     1 |          2 | True     | orders            | False           |                    55.5 |                       90 | True            |     34.5 | (83, 129)         | False                  |                               1 |                  0 |
| memory_leak   |   3003 | inventory |           1 |                     0 |          1 | True     | inventory         | False           |                    38.2 |                       48 | True            |      9.8 | (63, 285252)      | False                  |                               0 |                  0 |
| memory_leak   |   3004 | inventory |           1 |                     0 |          1 | True     | inventory         | False           |                    43.7 |                       62 | True            |     18.3 | (81, 502)         | False                  |                               1 |                  0 |
| traffic_surge |   3000 | web       |           0 |                     0 |          0 | False    | nan               | False           |                   nan   |                      nan | False           |    nan   |                   |                        |                               0 |                  0 |
| traffic_surge |   3001 | web       |           1 |                     0 |          0 | False    | nan               | False           |                   nan   |                      nan | False           |    nan   |                   |                        |                               1 |                  0 |
| traffic_surge |   3002 | web       |           0 |                     0 |          0 | False    | nan               | False           |                   nan   |                      nan | False           |    nan   |                   |                        |                               0 |                  0 |
| traffic_surge |   3003 | web       |           0 |                     0 |          0 | False    | nan               | False           |                   nan   |                      nan | False           |    nan   |                   |                        |                               0 |                  0 |
| traffic_surge |   3004 | web       |           0 |                     0 |          0 | False    | nan               | False           |                   nan   |                      nan | False           |    nan   |                   |                        |                               0 |                  0 |

`lead_s` = limit time (95% memory, disk threshold, restart or process death) minus first warning time; empty when no warning or the limit was never reached before the run ended (censored). `forecast_evidence_on_reactive` counts forecast evidence items attached to reactive incidents; they are not warnings. A warning is a timestamped forecast the engine attached to an incident, or a predicted incident (v3, docs/FORECAST_CHECK.md).
