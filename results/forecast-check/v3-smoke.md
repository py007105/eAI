# Forecast check (live, watch-only)

Design, definitions and pass criteria: `docs/FORECAST_CHECK.md`, fixed before the runs. Brain in watch-only mode, non-benchmark seeds, template LLM path not involved. Counts over the runs actually made; with 5 runs per scenario no rate or interval is claimed.

## Criteria

| criterion | result | detail |
|---|---|---|
| memory_leak: warning issued before the limit in at least 4 of 5 runs | FAIL | 1 of 1 runs |
| memory_leak: median lead time at least 30 s | PASS | median 37.1 s over 1 warned runs; leads [37.1] |
| memory_leak: warnings on the wrong service | PASS | 0 in 1 runs |
| disk_fill: warning issued before the limit in at least 4 of 5 runs | FAIL | 1 of 1 runs |
| disk_fill: median lead time at least 30 s | PASS | median 86.1 s over 1 warned runs; leads [86.1] |
| disk_fill: warnings on the wrong service | PASS | 0 in 1 runs |
| traffic_surge: warnings (any forecast warning) | PASS | 0 warnings in 0 healthy runs |
| good_deploy: warnings (any forecast warning) | PASS | 0 warnings in 0 healthy runs |
| watch-only: executed actions in every run | PASS | 0 executed actions in 2 runs |
| watch-only: an incident opened in each leak/disk run | PASS | 2 of 2 runs |

## Per run

| scenario    |   seed | target   |   incidents |   predicted incidents |   warnings | warned   | warning service   | wrong service   |   t_warn_after_inject_s |   t_limit_after_inject_s | limit_reached   |   lead_s | stated_window_s   | actual_inside_window   |   forecast_evidence_on_reactive |   executed_actions |
|:------------|-------:|:---------|------------:|----------------------:|-----------:|:---------|:------------------|:----------------|------------------------:|-------------------------:|:----------------|---------:|:------------------|:-----------------------|--------------------------------:|-------------------:|
| disk_fill   |   3901 | orders   |           2 |                     1 |          1 | True     | orders            | False           |                   213.9 |                      300 | True            |     86.1 | (88, 88)          | False                  |                               1 |                  0 |
| memory_leak |   3900 | web      |           2 |                     1 |          2 | True     | web               | False           |                    54.9 |                       92 | True            |     37.1 | (85, 135)         | False                  |                               1 |                  0 |

`lead_s` = limit time (95% memory, disk threshold, restart or process death) minus first warning time; empty when no warning or the limit was never reached before the run ended (censored). `forecast_evidence_on_reactive` counts forecast evidence items attached to reactive incidents; they are not warnings. A warning is a timestamped forecast the engine attached to an incident, or a predicted incident (v3, docs/FORECAST_CHECK.md).
