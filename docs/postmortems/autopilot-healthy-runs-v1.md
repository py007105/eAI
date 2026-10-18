# Metric surprise: the autopilot opened incidents on healthy runs and acted on traffic surges (v1)

Source: the 10 autopilot rows of `traffic_surge` and `good_deploy` (`results/benchmark-v1/benchmark_raw.jsonl`).

- `traffic_surge`: 5 of 5 runs opened an incident; in 4 of 5 the autopilot executed an action (`recreate_container` on `inventory` or `web`, after diagnosing `memory_leak`), counted as harmful interventions (any action in a healthy run). Failed-request % was 0.00 for no_action and for 4 of 5 other arms' surge cells, but 12.68% mean for the autopilot (0.00 to 18.40).
- `good_deploy`: 3 of 5 runs opened an incident; all were abstentions or pending incidents, and no action was executed.
- Pooled: healthy runs with a false alert 8 of 10 for the autopilot, against 0 of 10 for no_action, 5 of 10 for threshold_restart and 8 of 10 for prototype_rules. The README, DEMO and QA wording about healthy-negative behaviour must follow this table, not the design intent.
- In the surge runs the first incident ranked `inventory` first and was diagnosed `memory_leak` (e.g. seed 107: 8.0 s after opening, `recreate_container` executed at 16.6 s, verification "recovered"). A load surge on `web` is not a memory leak, so this contradicts the evidence the system was trained on (surges are a healthy class in the training data). The stored rows hold no confidence or feature values for these incidents (the evidence files for them were not preserved: only escalated incidents are preserved), so the reason cannot be established from v1 records.
- A second incident in several surge runs opened after the evaluator's `t_end` (e.g. seed 107: `down` on `web` 4 s after the scoring window ended); that is the evaluator's end-of-run restore, outside scoring, and is not counted as a fault by the scorer.

**Triage: (b) system bug candidate** (a classification that contradicts the evidence, with a harmful action), not confirmed in mechanism: the missing confidence and feature values prevent saying why the classifier answered `memory_leak`. Handling: report as recorded; candidate for v2 together with the incident-row logging proposal. Not classified as (c): the design says surges are healthy.
