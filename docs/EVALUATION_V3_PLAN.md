# Evaluation v3 (final evaluation under the plan rulebook): plan written before any run

Committed before any v3 run; the commit that contains this file is the reference. Results go to
`results/benchmark-v3/` (raw rows) and `docs/results/benchmark_v3.md`, rendered by `scripts/run_final_eval.py`.
Nothing here is changed after results are seen. A failed or missing run is reported as such.

## Why
Benchmarks v1 and v2 ran under a policy where autopilot also executed rollbacks and recreates on stateful services (the
reproduction is `eternalai/rulebooks/benchmark-v2.yaml`). The current default rulebook (`eternalai/rulebooks/default.yaml`,
the plan's values) changes what autopilot does without a person:
- autopilot runs only low risk;
- rollback is always high risk;
- recreate is high risk on orders, payments and inventory;
- error-spike and latency restarts are medium risk;
- payments is protected.

Every fault scenario is therefore policy-affected. The plan also asks for the memory-leak benchmark with and without
EternalAI.

## System under test
- **Code:** `plan-complete` at the pinned commit recorded in every row (`system_commit`); images built from that commit.
- **Models:** the frozen models (`models-v2`) + root margin 0.1215 + the knowledge base `data/kb` (all recorded in
  `/status`, which every row stores).
- **Rulebook:** `default.yaml` (recorded per row as `policy_file`).
- **Stack:** telemetry condition T3 (no Jaeger), as `scripts/demo.ps1`; LLM keys empty (template reports; as in v1/v2).

## Runs
Seeds: `seed = 600 + 10*repetition + scenario index` (the driver's rule). They lie outside training (1000+), v1 (100-149)
and v2.

| block | arm | scenarios | repetitions | runs |
|---|---|---|---|---|
| V3-A | `eternalai_autopilot`, unattended (no approver) | crash, latency, error_spike, memory_leak, disk_fill, bad_deploy, cpu_burn, traffic_surge, good_deploy | 5 | 45 |
| V3-B | `no_action` (no brain) | memory_leak | 5 | 5 |

Unattended autopilot means no person approves anything. A proposal that needs approval waits, expires after 120 s, and
is escalated. The run ends at its usual timeout (memory_leak 120 s, disk_fill 100 s, others 90 s) and is scored as
it stands. This measures what the plan's rulebook does when nobody is watching; it is not a measure of what a person
plus EternalAI achieves.

## Reported (descriptive; no pass/fail criteria)
Per scenario:
- runs;
- detected;
- recovered (EternalAI's own checkout verification);
- runs with an automatically executed action;
- runs where a proposal waited for approval;
- failed-request percentage (independent load-generator measure; mean, median, range);
- harmful interventions (an executed action on a non-target service);
- correct abstention on cpu_burn;
- incidents and actions on the healthy scenarios.

V3-B against V3-A memory_leak: failed-request percentage with and without EternalAI, same seeds (paired).

v1/v2 numbers are shown next to v3 only as labelled references ("benchmark-v2 policy"), never pooled.

## Known limits stated in the report
- One application, scripted faults, 5 seeds per cell.
- The seed-426 cpu_burn case (a wrong-service restart on an unseen fault) is a standing limitation. Five more cpu_burn
  runs do not establish safety on unseen faults.
