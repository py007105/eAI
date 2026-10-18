# v2 plan (REDUCED; pre-registered in Amendment 4 of `docs/EVALUATION_PLAN.md`, committed 2026-10-18T14:42:16+05:30 before any v2 collection or rerun)

v1 (tag `benchmark-system-v1`, 225 rows in `results/benchmark-v1/`) stays as recorded and is never replaced. v2 runs on fresh seeds and is reported beside v1. Hour estimates come from measured v1 run times (mean 3.4 min per evaluation run, 2.5 min per training run); they are estimates, not measurements of v2.

## Time against the budget

- v2 started at about 13:10 IST on 2026-10-18 (the user's v2 instruction, right after the forecast check was killed). At the time of this plan it is about 14:55 IST: **about 1 h 45 min elapsed** of the 30 h v2 budget (and of the 48 h horizon). Everything done so far was code, tests, diagnosis and pre-registration; the only Docker work was the reproduction runs and the 6 capture runs.
- Nothing starts until the user says "memory fixed". The 12 h buffer and the 14 h system freeze (from about 23:10 IST on 2026-10-19, T+34 h) are unchanged.

## What changed in the plan, and why

The first plan (about 45 Docker hours) assumed the v1 design (225-run scale, per-arm repetition of everything). The reduced plan keeps only runs that carry a claim. Three new findings also changed the content: the approval token bug is fixed and explained; the trace collector was dead during the whole v1 benchmark (hypothesis H7, a dead exporter's buffer adding several MB of memory under load, untested); and absolute memory limits cannot survive a few MB of drift, so v2 detects memory by growth against the service's own past (E2).

## Remaining Docker hours: about 10 (limit 20)

| stage | what | runs | stack hours | priority |
|---|---|---|---|---|
| 0 | Telemetry condition experiment: 6 level-40 surge runs (2 each: Jaeger up and capped / Jaeger down with exporter / SDK disabled), decided by the rule in Amendment 4 K | 6 | 0.7 | enables everything |
| 1 | Fresh training data: 34 runs (12 surge at both intensities, 6 good_deploy, 6 crashes on `orders`/`payments`, 10 other faults on previously uncovered targets), 45 min warm-up, two batches 60+ min apart, container ages logged | 34 | 3.2 (incl. warm-up and gap) | required for E3 |
| 2 | Retrain, cross-validate and freeze `models-v2`; build and tag `benchmark-system-v2` | 0 | 0 (CPU about 1.5 h with the stack stopped) | required |
| 3a | **P1** autopilot healthy: 12 surge + 12 good_deploy | 24 | 1.1 | safety claim |
| 3b | **P1** threshold_restart on the same 24 seeds (paired) | 24 | 1.1 | safety claim |
| 3c | **P1/P2** ask-first healthy: 4 surge + 4 good_deploy | 8 | 0.4 | shows no blocking |
| 3d | **P2** ask-first, 6 supported faults x 3 | 18 | 1.1 | validity of the fix |
| 3e | **P3** autopilot, 6 supported faults + cpu_burn x 3 | 21 | 1.2 | not materially worse than v1 |
| 3f | **P4** no_action, threshold_restart, prototype_rules on faults | 0 | 0 | not run; no claim made |
| reserve | reruns after a kill or a harness failure (20% of stage 3) | - | 1.0 | |
| **total** | | **135 runs** (95 evaluation) | **about 9.9** | |

Evaluation 95 runs is about 4.9 h of run time; with brain starts and the reserve about 6 h.

## Non-Docker work still to do (about 6 h)

E2 retraining and verification (1.5 h CPU, memory-heavy so with the stack down), building the v2 images (0.3 h), writing the evaluation summary tooling and v1/v2 side-by-side rendering for the reduced counts (1 h), triage and post-mortems (1.5 h), docs from the rendered tables (1.5 h). The live LLM check and three demo rehearsals stay in the buffer after the system freeze.

## Schedule from "memory fixed" (M)

| window | stage |
|---|---|
| M to M+0.7 h | Stage 0 |
| M+0.7 to M+1 h | apply the chosen condition, start the stack, preflight |
| M+1 to M+4.2 h | Stage 1 collection |
| M+4.2 to M+6.2 h | Stage 2 (stack stopped): retrain, freeze, tag |
| M+6.2 to M+12.2 h | Stage 3 evaluation and reserve |
| M+12.2 to M+16 h | triage, rendering, docs |

If M is within the next hour, all of it ends about 17 h after the v2 start, with more than 15 h left before the freeze. A slip of more than 4 hours, a memory failure that stops runs, or a change outside Amendment 4 is a stop-and-ask trigger.

## Surge intensity 40: needed?

**In the evaluation: yes, and it comes with the seeds** (8 of the 12 surge seeds draw 40, 4 draw 25). Level 25 already breaks v1 (6 of 6 captures), so level 40 is the harder, untrained-for case, and a fix that only works at 25 would not be a fix. **In the diagnostic capture: no further level-40 capture is needed for diagnosis**; the six remaining capture seeds are all level 40 and are used by Stage 0 (two per condition), so they give level-40 data at no extra cost. **In training: yes** (6 of the 12 fresh surge runs), otherwise the models would again never have seen it. The six finished level-25 captures stay as they are.

## Which containers v2 runs need

Needed: `web`, `orders`, `inventory`, `payments`, `prometheus`, `loadgen`, `evaluator`, and `eternalai` for every arm except `no_action`. Not needed: `dashboard` (not started for any v2 run) and `jaeger` (nothing reads it; the brain's code has no Jaeger client). Leaving Jaeger off is only safe together with `OTEL_SDK_DISABLED=true` on the apps (condition T3), because an exporter without a collector buffers spans in memory: that choice is made by the Stage 0 rule and then applied identically to the training collection, every arm and the baselines.

## Tooling added (scripts only, no system change)

`scripts/memguard.py` (waits and logs while free RAM is under a threshold; `--min-free-gb` default 1.0), `scripts/safe_collect.py` (resumable, atomic, memory-guarded training collector that logs container ages), `scripts/surge_capture.py` (atomic run files), and `run_benchmark.py` now waits for free RAM before each run. A guard that needs a change in `evaluator/` or the app is not required; none was made.

## Rules (unchanged)

Retraining only on the 72 original training runs plus fresh runs from unused training-block seeds; the v1 benchmark and the surge captures are seen data and are not used to train or to choose a threshold; no scenario name, surge flag or injection parameter reaches a model; no retuning after seeing v2 results (any further change is v3); the orders crash is not tuned for.
