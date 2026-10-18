# v2 documentation skeleton (PLACEHOLDERS ONLY: no number here is a result)

Every `{{...}}` is filled by `scripts/render_results.py --raw-v2 ...` and `scripts/evaluate_v2_criteria.py` output, never typed. Wording rule (Amendment 6): v2 = "fixes for the failures v1 exposed, tested on fresh seeds". Never "the model is better". No improvement is attributed to a single change.

## README (v2 paragraph, after the v1 findings)
- What v1 exposed: ask-first arm invalid (token and no TTL), incidents and actions on healthy runs, recovery self-reported, LLM path not exercised, forecast lead time not demonstrated.
- What v2 changed (four things together): retrained models ({{n_train_runs}} runs), memory features, approval-queue fix, telemetry condition T3.
- What the fresh-seed test showed: {{criteria_table}} (copied from `docs/results/v2_criteria.md`), demo decision {{demo_decision}}.
- What it cannot show: see the sample-size limits in EVALUATION.

## EVALUATION (v2 section)
1. Plan and amendments 4 to 6, deviations (Amendment 5: gap {{actual_gap_min}} min).
2. Results: `docs/results/benchmark_v2.md` (section 8 side by side, unpaired, different seeds).
3. Criteria 1 to 7: {{criteria_table}}; failed criteria stated as failed.
4. Non-recoveries and triage classes: {{triage_summary}}.
5. Limitations: reduced plan (95 runs), 3 runs per cell, no v2 baselines on faults, recovery self-reported, T3 differs from the v1 telemetry condition, mixed-condition training data, forecast lead time {{forecast_status}}.

## DEMO
- Condition: T3 stack via `scripts/demo.ps1`; the dashboard is on (documented difference). Rehearsal 1 runs with the dashboard on and compares incident/action counts on a healthy surge and one fault with {{dashboard_rehearsal_result}}.
- Which system is shown: {{v1_or_v2}} per rule P; issues stated: {{issues}}.
- Three rehearsals: {{rehearsal_log}}.

## QA_FOR_JUDGES additions
- Why is v2 shown (or not)? {{demo_decision}}.
- What was the gap deviation? Amendment 5.
- Did the trace collector cause v1's memory shift? HYPOTHESIS only: `docs/postmortems/telemetry-conditions-by-batch.md`.
- LLM report provider in v2: {{llm_provider_status}}.

## MODEL_CARD
- Training data: 72 original + 34 fresh runs, data hash {{data_hash}}, mixed telemetry conditions (72 exporter on, 34 off); limitations as above.
