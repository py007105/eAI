# Live LLM check (Step 3), five non-benchmark incidents - set A gemini-3.8-flash (pinned default)

Seeds 2100-2105 (set A) or 2110-2115 (set B) (outside every benchmark and training range), autopilot, the brain started with the Gemini key from `.env` (key value never printed). These are not benchmark rows and are not added to any evaluated count. The deterministic decision is made before any LLM call; the LLM only writes the report text. A comparison with the evaluated v2 autopilot rows is about behaviour, not statistics: n = 5 here and different seeds.

## Per incident

| scenario | seed | target | provider that answered | LLM latency s | fallback reasons | LLM disagreed | LLM runbook suggestion | executed (deterministic) | verification | seconds to verified recovery | failed-request % |
|---|---|---|---|---|---|---|---|---|---|---|---|
| crash | 2100 | payments | template | 20.06 | gemini: ReadTimeout | False | - | restart_service@payments | recovered | 41.3 | 14.24 |
| latency | 2101 | payments | template | 13.95 | gemini: HTTPStatusError | False | - | restart_service@payments | recovered | 52.4 | 0.85 |
| error_spike | 2102 | payments | template | 20.07 | gemini: ReadTimeout | False | - | restart_service@payments | recovered | 41.6 | 7.77 |
| memory_leak | 2103 | web | template | 20.11 | gemini: ReadTimeout | False | - | recreate_container@web | recovered | 47.9 | 3.77 |
| bad_deploy | 2105 | orders | template | 20.08 | gemini: ReadTimeout | False | - | rollback_release@orders | recovered | 59.8 | 11.28 |

## Per call summary

- incidents with a report call: 5; calls attempted (answered + failed): 5; answered and schema-valid: **0/5**
- latency of the report path per incident (seconds; includes failed attempts and the fallback; max is bounded by the per-request timeout of 20 s per provider): 13.9, 20.1, 20.1, 20.1, 20.1
- 'schema-valid' here means the provider answered and the strict validator accepted it. A timeout is not a schema failure; it is listed under fallback reasons.

## Evaluated v2 autopilot behaviour for the same scenarios (valid rows, other seeds, template reports)

| scenario | evaluated n | executed runbooks | seconds to verified recovery (values) | live check seconds | same runbook as evaluated |
|---|---|---|---|---|---|
| bad_deploy | 3 | rollback_release | 59.3 58.0 59.7 | 59.8 | True |
| crash | 3 | restart_service | 42.3 40.3 39.4 | 41.3 | True |
| error_spike | 3 | restart_service | 42.9 41.3 42.1 | 41.6 | True |
| latency | 3 | restart_service | 51.2 47.8 50.5 | 52.4 | True |
| memory_leak | 3 | recreate_container | 46.3 45.6 43.0 | 47.9 | True |

# Live LLM check (Step 3), five non-benchmark incidents - set B gemini-3.5-flash-lite (GEMINI_MODEL override)

Seeds 2100-2105 (set A) or 2110-2115 (set B) (outside every benchmark and training range), autopilot, the brain started with the Gemini key from `.env` (key value never printed). These are not benchmark rows and are not added to any evaluated count. The deterministic decision is made before any LLM call; the LLM only writes the report text. A comparison with the evaluated v2 autopilot rows is about behaviour, not statistics: n = 5 here and different seeds.

## Per incident

| scenario | seed | target | provider that answered | LLM latency s | fallback reasons | LLM disagreed | LLM runbook suggestion | executed (deterministic) | verification | seconds to verified recovery | failed-request % |
|---|---|---|---|---|---|---|---|---|---|---|---|
| crash | 2110 | web | gemini | 1.24 | - | False | restart_service | restart_service@web | recovered | 39.6 | 32.35 |
| latency | 2111 | payments | template | 0.1 | gemini: ConnectError | False | - | restart_service@payments | recovered | 49.3 | 1.81 |
| error_spike | 2112 | web | gemini | 1.39 | - | False | restart_service | restart_service@web | recovered | 44.0 | 17.56 |
| memory_leak | 2113 | web | gemini | 1.62 | - | False | recreate_container | recreate_container@web | recovered | 47.6 | 3.73 |
| bad_deploy | 2115 | payments | gemini | 1.23 | - | False | rollback_release | rollback_release@payments | recovered | 61.6 | 11.59 |

## Per call summary

- incidents with a report call: 5; calls attempted (answered + failed): 5; answered and schema-valid: **4/5**
- latency of the report path per incident (seconds; includes failed attempts and the fallback; max is bounded by the per-request timeout of 20 s per provider): 0.1, 1.2, 1.2, 1.4, 1.6
- 'schema-valid' here means the provider answered and the strict validator accepted it. A timeout is not a schema failure; it is listed under fallback reasons.

## Evaluated v2 autopilot behaviour for the same scenarios (valid rows, other seeds, template reports)

| scenario | evaluated n | executed runbooks | seconds to verified recovery (values) | live check seconds | same runbook as evaluated |
|---|---|---|---|---|---|
| bad_deploy | 3 | rollback_release | 59.3 58.0 59.7 | 61.6 | True |
| crash | 3 | restart_service | 42.3 40.3 39.4 | 39.6 | True |
| error_spike | 3 | restart_service | 42.9 41.3 42.1 | 44.0 | True |
| latency | 3 | restart_service | 51.2 47.8 50.5 | 49.3 | True |
| memory_leak | 3 | recreate_container | 46.3 45.6 43.0 | 47.6 | True |
