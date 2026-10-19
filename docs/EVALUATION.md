# Evaluation

Status: **benchmark v1 and the reduced v2 evaluation are finished; this file holds methods, the canonical v2 methodology and limitations, and a short v1 results summary.** Every result comes from a script that renders tables from raw result
files (`scripts/render_results.py` for the benchmark, the training and evaluation scripts for the rest). This file links to those generated files and never retypes
their numbers. Rules for the held-out benchmark are fixed in `docs/EVALUATION_PLAN.md`, which predates the results.

> **Three findings first (benchmark v1, `docs/results/benchmark.md`; not buried, not softened):**
> 1. **The ask-first arm is invalid.** The benchmark harness handed the brain and the simulated operator the placeholder token `change-me` (an import of the config module loaded it from `.env`), so the brain refused every approval (HTTP 503) and the operator ignored the refusal; the first proposal then sat unapproved and, because a pending approval never expires, blocked all later detection (42 of 45 runs). Its 0 of 30 recoveries say nothing about ask-first operation (`docs/postmortems/ask-first-arm-stuck-incident-v1.md`). Both faults are fixed on the v2 branch and evaluated on fresh seeds.
> 2. **False alarms on healthy runs.** The autopilot opened an incident in 8 of 10 healthy runs and recreated a container in 4 of 5 traffic surges (it called a surge a memory leak). threshold_restart had 5 of 10 false alerts and prototype_rules 8 of 10 (`docs/postmortems/autopilot-healthy-runs-v1.md`).
> 3. **Recovery is self-reported.** It comes from the system's own checkout; the independent measure is the load generator's failed-request %. No independent probe logs exist.
>
> Also true: the benchmark brains were configured without LLM keys (the report provider is not recorded per run), forecasting is implemented and unit-tested but its live lead time was not demonstrated (an attempted live check was stopped by low memory, and two smoke runs ended before the resource limit), and 27 of 30 autopilot runs reporting recovery is one application, five runs per cell, scripted faults. This box describes benchmark v1, which is kept unchanged; the v2 evaluation that followed is described below and in the canonical section of `docs/EVALUATION.md`.

<!-- gen:eval_v2 -->
## Canonical methodology, results and limitations: benchmark v2 (final)

This section is the single place where the v2 caveats are written out in full. The README, the demo script and the judge Q&A refer here instead of repeating them. Every number below is filled in by `scripts/build_docs.py` from the exported rows (`results/benchmark-v2/rerun/`); the full tables are in `docs/results/benchmark_v2.md` (rendered by `scripts/render_v2_report.py`) and `docs/results/benchmark_v1_v2.md` (side by side). Nothing here is typed by hand.

### What v2 is, and the wording rule (Amendment 6)

v2 is **fixes for the failures v1 exposed, tested on fresh seeds**. It is not evidence that "the model is better". v2 differs from v1 in four things that changed together: the retrained models (72 original + 34 fresh training runs), the memory features (relative growth instead of absolute levels), the approval-queue fix (time-to-live, non-blocking pending approvals, a real benchmark token) and the telemetry condition (T3: trace exporter off, no collector). **No improvement or change is attributable to any single one of them.** v1 and v2 are **unpaired** (v1 seeds 100-148, v2 seeds 200-318 plus the replacement block 400-429) and v2 is a **reduced plan** (Amendment 4 section M): three autopilot, three ask-first and no baseline run per supported fault, twelve autopilot and twelve threshold_restart and four ask-first runs per healthy scenario. Any statement about telemetry is a HYPOTHESIS unless a controlled test exists (`docs/postmortems/telemetry-conditions-by-batch.md`).

### Run accounting, exclusions and replacement runs (Amendment 8)

- Evaluated set: **95** rows = **58 valid original rows + 37 replacement rows**.
- During Stage 3 the inventory service ran out of stock (it only subtracts stock; there is no add-stock endpoint). It was first noticed from the result pattern (every verification probe answered HTTP 409) and then confirmed against stock records. **37 original rows** whose run ended after the last confirmed in-stock checkout (23:30:36 IST on 2026-10-18) were marked invalid by a timestamp rule fixed before any row was classified, applied mechanically (also to rows that looked clean). They stay in `benchmark_v2_raw.jsonl` and in `invalid_rows.json`; none was deleted.
- **The replacement runs were designed after the problem was discovered.** The rule was committed before any restock or re-run and uses stock timestamps, not outcomes, but a reader should know the sequence. Of the 37 replacement runs, **2 reused the original seed** (the partner arm's row was valid, so pairing was kept) and **35 used fresh seeds** from a block pre-checked for overlap (19 distinct seeds, 400-426).
- Replacement runs ran behind a **stock gate** (harness tooling, direct SQL restock because adding an endpoint would be a system change, verified through `GET /items`; 1 restock was needed; lowest stock after any replacement run: 95230). The gate and the per-run stock record exist **only for the replacement runs**. The original valid rows had neither.
- Other harness differences, stated: replacement runs were one `run_benchmark.py` invocation each, in ascending seed order, and the `rep` field is 0; one run (disk_fill seed 204, evaluator run 8e932d23e9) finished after a driver crash and has no row (excluded; it is still in the evaluator export); the original Stage 3 had one memory kill and one automatic resume. Telemetry condition T3, the models, the arms and the scoring were unchanged.
- **Stock evidence:** a log-proven timeline exists for **one SKU only** (`sku-mug`, the verification probe's SKU). The other three SKUs are supported by indirect observations only (similar consumption, the load generator's random SKU choice, and the service seeding the same level for each; no inventory logs survive). The 72 original training runs, the 34 fresh runs and the v1 benchmark were checked for a stock-out signature **without finding one**; that is absence of evidence in the records that exist (`docs/results/stock_validity.md`).

### Pre-registered criteria (Amendment 4 section N) and what was observed

| # | criterion | verdict | counts |
|---|---|---|---|
| 1 | ask-first: approve_failures == 0, thread_errors == 0, all 18 supported detected, >= 15/18 recovered | **PASS** | runs 26; approve_failures 0; thread_errors 0; rows without approver stats 0; detected 18/18; recovered 18/18 |
| 2 | autopilot healthy: <= 2/24 runs open an incident and no more than threshold_restart on the same seeds | **PASS** | autopilot 1/24; threshold_restart 6/24 (on autopilot's incident seeds: 6) |
| 3 | 0 executed actions in the 24 autopilot and 8 ask-first healthy runs | **PASS** | autopilot runs with an action 0/24; ask-first 0/8 |
| 4 | autopilot supported: all 18 detected and mean detection <= 15.1 s | **PASS** | detected 18/18; mean detection 11.78 s |
| 5 | autopilot supported: >= 15/18 recovered, no cell below 2/3 (crash 1/3) | **PASS** | recovered 18/18; cells crash 3/3, latency 3/3, error_spike 3/3, memory_leak 3/3, disk_fill 3/3, bad_deploy 3/3 |
| 6 | autopilot supported: pooled mean failed-request % <= 23.4 | **PASS** | mean 11.15% over 18 runs |
| 7 | cpu_burn: abstained correctly in >= 2 of 3 | **PASS** | abstained 2/3 |

All seven passed, so by the pre-registered rule P the demo may show v2. **Passing criteria written with a reduced sample is not a measurement of reliability.** How much certainty the counts carry (Wilson 95% intervals, treating runs as independent, which flatters them):

- Supported faults, autopilot: **18/18 [82%, 100%] detected, 18/18 [82%, 100%] recovered** by its own verification. With 18 runs, a perfect count is still consistent with a true success rate as low as about 82%. Each fault type has n = 3 (a perfect 3/3 is consistent with a rate as low as 44%), so no per-fault claim is made.
- Healthy runs, autopilot: **1/24 [1%, 20%]** opened an incident and **0/24 [0%, 14%]** executed an action. One incident in 24 is consistent with a true rate anywhere up to about 20%. The one incident was in a traffic surge (1/12 surge runs opened one). The same-seed threshold_restart baseline opened 6/24 [12%, 45%]; ask-first opened 0/8 [0%, 32%] with 0/8 [0%, 32%] actions.
- Ask-first: 18/18 [82%, 100%] detected and 18/18 [82%, 100%] recovered, zero approval failures (v1's ask-first arm was invalid, see the postmortem, so there is no valid v1 comparison).
- Mean failed-request % over the 18 supported autopilot runs: 11.15; mean detection 11.78 s. For reference, v1 autopilot (different seeds) was 18.39% and 12.1 s; the v1 no-action arm was 32.17%. **The detection times are a tie within noise; the failed-request figures are not comparable** (different seeds, fault targets and conditions).

### How recovery is judged (and what that does not prove)

**Recovery is verified internally**: the brain's own synthetic checkout through web, orders, inventory and payments over a window. The **failed-request %** is an independently measured **impact metric** (the evaluator reads the load generator's counters), but it is not complete independent proof of recovery: no `no_action` arm exists in v2 to give a same-seed reference, there are no independent probe logs, and a low failed-request % can also occur when a fault never hurt the user path (disk_fill rows show 0.0%). Treat "recovered" as "the system's own check passed", supported but not proven by the impact metric.

### Baseline comparisons

There is **no paired v2 baseline comparison for supported faults** (only autopilot and ask-first ran on them), so nothing here claims EternalAI is better than a restart-on-threshold script at recovering faults. The only same-seed baseline in v2 is `threshold_restart` on healthy runs (6/24 [12%, 45%] incidents against 1/24 [1%, 20%] for the autopilot, same seeds). v1's baseline comparison (no_action, threshold_restart, prototype_rules) is on different seeds and an older system version; it is unpaired with v2, and in v1 the autopilot was not ahead on several metrics (listed above). Extension B (an autopilot / threshold_restart / no_action comparison on the supported faults, planned as Amendment 9) was **skipped by the pre-set rule**: it needs at least 10 hours before the system freeze, and on 2026-10-19 at 15:11 IST there were about 8 hours before the freeze at 23:10 IST (the sample sizes, the run time and the margin needed for rehearsals and release checks did not fit).

### Unseen fault: cpu_burn (no runbook, never in training)

- v2: the autopilot **abstained in 2/3** runs; v1: it abstained in **4/5**. These are different versions on different seeds and are **not pooled into one rate**. Neither supports a claim that EternalAI "abstains on unseen faults" or "knows when to stop".
- **Seed 426 (v2) is a failure.** The injected fault was on `orders`. The ranker put `orders` **3rd**, the novelty score (0.61) was below the abstention threshold (1.12) and the class confidence (0.58) was above the abstain limit, so the autopilot restarted `inventory`, a service that was not the target. Failed requests were 27.71% and the verification checkouts were 0/4 (ReadTimeout). The scorer flags this as "harmful" only by its definition (an executed action on a service other than the injected target); **whether the restart added damage is unknown** (no unrestarted control for that seed, and Prometheus no longer holds the window). Conclusion, accepted: a **model generalisation limitation**; an implementation defect is not evidenced but not ruled out. **Decision: not fixed before the freeze** (a fix would be v3 on fresh seeds). Full timeline: `docs/postmortems/cpu_burn_seed426.md`.

### Training data and telemetry conditions

The retrained models were trained on **two telemetry conditions**: the 72 original runs with the trace exporter on (collector state during that period was not recorded) and the 34 fresh runs with it off (T3). The condition is not a model input and cross-validation folds mix both, so cross-validation cannot separate its effect. v1's benchmark ran with the exporter on and the collector dead; v2 ran under T3. **HYPOTHESIS, not a finding:** that the dead collector explains the v1 memory shift (`docs/postmortems/telemetry-conditions-by-batch.md`); the supporting Stage 0 diagnostic had two runs per condition.

### Health-log coverage

An external container health log (`scripts/health_watch.py`, once a minute, read-only) exists only from 2026-10-19 00:29:31 IST. Original valid rows that ran before then, including the P1 runs and the first ask-first fault runs, are **not covered** by it, so a container fault outside the brain's own record could not be excluded for those runs. All 37 replacement runs are covered. A once-a-minute sampler can miss a short restart; seven replacement rows show a single-sample "exited" state explained by the injected crash or the brain's start.

### What remains undemonstrated

- **Forecast lead time**: forecasting is implemented and unit-tested, but its live lead time was not demonstrated.
- **Groq** was never tested (no key was available).
- **Gemini**: see the LLM paragraph in section 5 (Limitations) for the tests actually performed; the benchmark brains ran without LLM keys, so the LLM did not contribute to any benchmark number.
- **Other applications**: nothing was tested on another application.

### Deviations, exclusions and amendments, in order

Amendment 4 (reduced v2 plan, pass criteria, demo rule P, triage classes) · Amendment 5 (Stage 1 record, longer gap between runs) · Amendment 6 (this wording rule) · Amendment 7 (external health log, 2026-10-19 00:29 IST) · Amendment 8 (stock-out, exclusion rule, direct-SQL restock as a harness action, replacement plan). All are in `docs/EVALUATION_PLAN.md`. The criteria were not changed after any result was read. Original files are kept, replacements are in their own files, and the evaluated set is a derived file (`scripts/v2_combine.py`) that can be rebuilt; checksums: `results/benchmark-v2/SHA256SUMS` and `SHA256SUMS-rerun`.
<!-- /gen:eval_v2 -->

## Results summary (benchmark v1)

| arm (v1) | self-reported recovery, 30 supported runs | failed-request % (mean) | seconds to self-reported recovery (mean) | healthy runs with a false alert (of 10) | harmful interventions on healthy runs |
|---|---|---|---|---|---|
| no_action | 0 | 32.17 | - | 0 | 0 |
| threshold_restart | 12 | 26.60 | 68.2 | 5 | 0 |
| prototype_rules | 9 | 26.29 | 69.4 | 8 | 0 |
| eternalai_ask_first (invalid, see finding 1) | 0 | 31.99 | - | 0 (detection blocked) | 0 |
| eternalai_autopilot | 27 | 18.39 | 50.0 | 8 | 4 |

Source: `docs/results/benchmark.md`, sections 1b and 4 (rendered from `results/benchmark-v1/benchmark_raw.jsonl`). Where the autopilot does **not** beat the baselines: threshold_restart recovered `crash` in 4 of 5 runs against the autopilot's 2 of 5 (both orders crashes abstained); on `latency` the autopilot's failed-request % (8.1) is higher than threshold_restart's (4.0), and on `memory_leak` it is higher than no_action's (11.2 against 0.4) because its own container recreation fails requests; its false-alert count on healthy runs is worse than threshold_restart's and equal to prototype_rules'; and the pooled failed-request % and detection-time differences against threshold_restart and prototype_rules have intervals that include zero, so they are not distinguishable at n = 5 per cell.

Offline root-cause baselines on the 72 training runs (labelled offline, not a live arm): `docs/results/offline_rca_baseline.md`. Post-mortems and the triage of all 72 non-recoveries: `docs/postmortems/`. Forecast check: attempted, stopped by low memory, not completed; two smoke runs could not measure lead time because runs ended before the limit, so forecasting is stated everywhere as "implemented and unit-tested; live lead time not demonstrated".

## 1. What is evaluated, and on what

| part | data | protocol | generated results |
|---|---|---|---|
| Workbook quality | the supplied 17-sheet training workbook | profiling only | `docs/DATA_QUALITY.md` |
| Fault classification on public data | RCAEval RE1 (3 systems, metrics only), 300 incidents | grouped CV by incident, and leave-one-system-out | `docs/results/rcaeval_re1.md` |
| Cross-system transfer experiments | the same RE1 rows | leave-one-system-out with bootstrap intervals; feature selection on the training systems only | `docs/results/transfer_re1.md` |
| Detector, classifier, abstention, ranker on the live application | live runs from this repository's own stack, training seeds | grouped CV by run, thresholds chosen inside training folds, hold-one-fault-type-out | `docs/results/models_cv.md`, `window_sweep.md`, `detector_margin.md` |
| End-to-end recovery | the evaluator injects faults on **unseen seeds** while the system runs | paired benchmark, 5 arms x 9 scenarios x 5 repetitions | `docs/results/benchmark.md` (rendered from `benchmark_raw.jsonl`) |
| LLM report layer | a fixed fake incident and, later, real incidents | schema validity and latency per provider | `docs/results/llm_smoke.md` |

Results are kept in separate tables for public-dataset, own-application and cross-system evidence; they are not blended into one score.

## 2. Methods

**Data.** Three sources, never merged row-wise: the workbook (label quality findings, runbook text, label mapping), RCAEval RE1 (public lab telemetry for cross-system evidence), and
live runs generated by the independent evaluator on this repository's four-service application (training seeds 1000-1707). See `docs/DATA.md`, including the development log of what went wrong and why.

**Features.** One rolling-window code path (`eternalai/features/window.py`) is used for training and for live inference. Missing data stays missing (explicit observed-masks, NaN-aware models). The window length (10 s)
was chosen by cross-validation (`docs/results/window_sweep.md`).

**Models** (frozen as git tag `models-v1`, see `docs/MODEL_CARD.md`): learned healthy-range limits plus an IsolationForest per service (detector); gradient boosting with temperature scaling and a novelty gate
(classifier, with abstention); gradient boosting over topology and timing evidence (root-cause ranking); a Theil-Sen trend forecaster for gradual memory and disk growth.

**Splits and leakage controls.** All splits are by whole run (or whole incident, or whole system); preprocessing, calibration, thresholds and feature selection are fitted on training folds only; the abstain threshold is chosen by
an inner cross-validation inside each training fold; label-bearing columns are excluded from model inputs; a data check (`models/check_runs.py`) tests for leakage and for run-order effects before any training;
cpu_burn is never used in training and serves as the unseen fault.

**Benchmark.** Five arms share the same executor, policy engine, verification and incident de-duplication and differ only in the brain: no action; fixed thresholds then restart; the earlier prototype's rules ported onto this
stack; EternalAI with a simulated approving operator (ask-first); EternalAI in autopilot. The same seeds are used in every arm, so every arm faces the same fault on the same service. Details, metric definitions, the
failure triage rule and the rules for harness failures are in `docs/EVALUATION_PLAN.md`.

**How recovery is judged.** Recovery is **self-reported** by the system under test (its own synthetic-checkout verification); the evaluator contributes an independent failed-request percentage from the load generator.
This is a stated limitation of v1, with a consistency check described in the plan.

**LLM layer.** The model returns JSON validated against a strict schema; evidence ids must exist, the runbook must be one the deterministic table allows for the diagnosed cause, and the engine's own diagnosis stays
authoritative. Actions never depend on the LLM. The benchmark brains were started with both LLM key variables empty (by construction), so reports are expected to be template reports; the report provider is not recorded in the result rows (design limitation, class c), and `scripts/render_results.py` counts timelines containing a `report by <provider>` line as a consistency check.

## 3. Reproduce

```
python data/clean_workbook.py --workbook <workbook.xlsx>          # data-quality report and cleaned tables
python data/download_rcaeval.py --systems OB SS TT                # RCAEval RE1 (about 370 MB)
python data/build_rcaeval_features.py && python models/eval_rcaeval.py && python models/eval_transfer.py --boot 500
docker compose --profile releases build && docker compose up -d   # the stack
python models/collect_runs.py --reps 8                            # training runs through the evaluator
python models/check_runs.py                                       # data sanity check before any training
python models/train_models.py --window 10                         # train, cross-validate, save artifacts (also --sweep, --detector-sweep)
python scripts/model_card.py
powershell -File scripts\run_all_arms.ps1                         # the held-out benchmark (about 12 hours)
python scripts/benchmark_status.py                                # read-only progress
python scripts/render_results.py                                  # every benchmark table, from the raw rows
python scripts/llm_smoke.py                                       # needs GEMINI_API_KEY and/or GROQ_API_KEY in .env
python -m pytest                                                  # unit and regression tests (live LLM tests: pytest -m live)
```

Every results file records the Python and package versions, the hardware, the seeds and (where relevant) the data hash.

## 4. Results

Rendered by scripts, not typed: v1 `docs/results/benchmark.md`; v2 `docs/results/benchmark_v2.md`; v1 and v2 side by side (unpaired, different seeds) `docs/results/benchmark_v1_v2.md`. The headline v2 counts and their intervals are in the canonical section at the top of this file.

## 5. Limitations

- **v2: No per-run container-state record in v2. An external health log exists from 2026-10-19 00:29:31 IST onward (`results/benchmark-v2/health_log.tsv`, written by `scripts/health_watch.py`, once a minute, read-only). Runs before that are not covered, including the P1 runs and the first ask-first fault runs. Triage checks each later run's time window against this log and marks any run during which a required container was unhealthy or restarted unexpectedly.**
- **v2: Inventory stock-out (Amendment 8).** The inventory service only subtracts stock, and the stock ran out during Stage 3; 37 v2 rows ending after the last confirmed in-stock checkout were marked invalid and re-run behind a stock gate (a direct SQL restock by the harness, because the service has no add-stock endpoint). **Only one SKU (`sku-mug`, the verification probe's SKU) has a log-proven stock timeline; the other three are indirect** (similar consumption and the same random SKU choice by the load generator; no inventory logs survive). The 72 original training runs, the 34 fresh runs and the v1 benchmark were checked for a stock-out signature (persistent checkout failures, HTTP 409 probes, healthy-run failed-request %) **without finding one** (`docs/results/stock_validity.md`); that is absence of evidence from the records that exist, not a proof for the three indirect SKUs. The stock gate and the per-run stock record exist only for the re-runs.

- **v2 summary of limits (numbers and intervals are in the canonical section at the top):** n = 3 per fault type, so no per-fault claim; v1 and v2 are unpaired and on different seeds; four changes went in together, so no improvement is attributable to any one of them; no paired v2 baseline for supported faults and no no_action arm (so the failed-request % has no same-seed reference); recovery is verified internally and the failed-request % is an impact metric, not independent proof; replacement runs were designed after the stock-out was seen; training mixes two telemetry conditions; health-log coverage starts at 2026-10-19 00:29:31 IST; forecast lead time is undemonstrated; Groq is untested; one application.
<!-- gen:limits_v2 -->
- **v2: cpu_burn.** The autopilot abstained in 2/3 v2 runs and 4/5 v1 runs of this one unseen fault (different versions and seeds; not pooled into one rate). In v2 seed 426 it restarted `inventory` while `orders` was the target, ranked the target number 3, and the failed-request % was 27.71 with 0/4 checkout probes passing. "Harmful" in the scorer means only an executed action on a service other than the injected target; the added damage, if any, is unknown. Classified as a model generalisation limitation; **decision: not fixed before the freeze** (a fix would be v3 on fresh seeds). We make no claim that the system abstains on unseen faults or knows when to stop (`docs/postmortems/cpu_burn_seed426.md`).
- **LLM report layer, what was actually tested (2026-10-19, `docs/results/llm_live.md`, `tests/test_llm_isolation.py`).** The report text is produced off the recovery path: the deterministic template report and the runbook are fixed and proposed before the LLM thread starts, the thread holds no engine lock while it waits, nothing on the decision or action path (policy, executor, verification, ranking, classification) references the LLM module, the LLM output must validate against a strict schema and an allowed-candidate runbook, and a disagreeing answer is recorded and overridden by the engine; 12 isolation tests pass against the system code. The per-request timeout is 20 s per provider (a per-phase httpx timeout, not a total wall-clock bound; it is harmless to recovery because the call is in a background thread, but it is not a strict ceiling on report latency). **Live Gemini, five incidents with the pinned default model (`gemini-3.8-flash`): 0/5 answered with a schema-valid report; 4 timed out at 20 s and 1 failed with an HTTP error, so the template report was used each time and recovery was unaffected** (a direct probe showed that model answering in 8 to 77 s or not at all within 100 s, because it spends its time on internal reasoning). **Five more incidents with the faster `gemini-3.5-flash-lite`, set through the existing `GEMINI_MODEL` variable (a config override, no code change): 4/5 answered with a schema-valid report in 1.2-1.6 s; the other fell back to the template after a connection error.** In both sets all incidents recovered (5/5 and 5/5), with the same runbooks as the evaluated runs and times to verified recovery of 41.3-59.8 s (set A) and 39.6-61.6 s (set B), within the range of the evaluated rows for the same scenarios. In set B the model's runbook suggestion equalled the deterministic runbook in every answered case; five samples are not proof of decision independence, which rests on the code-path analysis and the tests. These ten incidents are outside the frozen v2 evaluation. **Groq is untested** (no key).
- **v2: a second incident and a second action for one fault.** 2 of the 36 evaluated fault runs opened more than one incident and 2 executed more than one action for the same injected fault (disk_fill seed 414 (ask_first), disk_fill seed 414 (autopilot); script: `scripts/multi_incident_check.py`, table `docs/results/multi_incident.md`). The runs still recovered with the same runbook (`clear_temp_path`). The same pattern appeared once in a headless demo rehearsal (disk_fill, two incidents, two `clear_temp_path` runs; `docs/results/demo_rehearsals.md`). This is a **known limitation, not investigated and not fixed** (any fix would be v3): a repeated action is a repeated intervention on a service, which the circuit breaker only stops after two.
<!-- /gen:limits_v2 -->
- **Small training set.** 72 live runs were collected (71 used after one was excluded as corrupted): 8 per scenario for a handful of fault types.
- **One application, controlled faults.** Four Python services, one machine, one workload generator, faults injected by a script. Nothing here was tested on a different application.
- **RE1 is laboratory telemetry,** not production data, and its disk fault is I/O stress rather than a full disk, its memory fault is stress rather than a leak.
- **Cross-validation scores are optimistic.** They were produced after four iterations on the same data, and on the same distribution that the models were trained on. They are not a forecast of performance elsewhere. The benchmark on unseen seeds is the real test,
  and even it uses the same fault injector that produced the training data.
- **n = 5 per cell** in the benchmark: no significance claims between arms are made from individual cells.
- **Recovery is self-reported** by the system under test (see above); there are no independent probe logs in v1.
- **Training and benchmark fault delivery differ slightly** for the leak and disk faults (see `docs/DATA.md`).
- **The ported prototype baseline is approximate**, and the simulated operator always approves after a fixed delay.
- **The learned detector's forest adds nothing measurable** over the learned limits; the classifier's near-perfect cross-validation scores reflect strong, cleanly injected faults.
- **LLM:** the Gemini path was verified with a few real calls on 2026-10-17 (9 generateContent requests in total; 4 used the project's real prompt: 2 before the response-schema constraint, both failing validation, and 2 after it, both valid). It is not a measurement of
  reliability. **Groq is untested** (no key was available). The summaries the model writes are constrained and checked for evidence ids and runbook choice, but their prose is not fact-checked beyond that.
- **Security.** The backend mounts the Docker socket (root-equivalent on the host); the approval API is refused until a real token is set. This is a demo configuration, not a hardened deployment.
- **Dashboard screenshots** in `docs/screenshots/` use fixture data and show layout only.
