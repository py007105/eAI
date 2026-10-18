# Evaluation

Status: **benchmark v1 finished; this file holds methods and a short results summary.** Every result comes from a script that renders tables from raw result
files (`scripts/render_results.py` for the benchmark, the training and evaluation scripts for the rest). This file links to those generated files and never retypes
their numbers. Rules for the held-out benchmark are fixed in `docs/EVALUATION_PLAN.md`, which predates the results.

> **Three findings first (benchmark v1, `docs/results/benchmark.md`; not buried, not softened):**
> 1. **The ask-first arm is invalid.** The benchmark harness handed the brain and the simulated operator the placeholder token `change-me` (an import of the config module loaded it from `.env`), so the brain refused every approval (HTTP 503) and the operator ignored the refusal; the first proposal then sat unapproved and, because a pending approval never expires, blocked all later detection (42 of 45 runs). Its 0 of 30 recoveries say nothing about ask-first operation (`docs/postmortems/ask-first-arm-stuck-incident-v1.md`). Both faults are fixed on the v2 branch and evaluated on fresh seeds.
> 2. **False alarms on healthy runs.** The autopilot opened an incident in 8 of 10 healthy runs and recreated a container in 4 of 5 traffic surges (it called a surge a memory leak). threshold_restart had 5 of 10 false alerts and prototype_rules 8 of 10 (`docs/postmortems/autopilot-healthy-runs-v1.md`).
> 3. **Recovery is self-reported.** It comes from the system's own checkout; the independent measure is the load generator's failed-request %. No independent probe logs exist.
>
> Also true: the benchmark brains were configured without LLM keys (the report provider is not recorded per run), forecasting is implemented and unit-tested but its live lead time was not demonstrated (an attempted live check was stopped by low memory, and two smoke runs ended before the resource limit), and 27 of 30 autopilot runs reporting recovery is one application, five runs per cell, scripted faults. v2 is a proposal only (`docs/V2_PROPOSAL.md`).

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

Not yet written. The benchmark tables will be rendered into `docs/results/benchmark.md` and linked here, with v1 and v2 side by side if a v2 exists. Until then this section intentionally contains no numbers.

## 5. Limitations

- **v2: No per-run container-state record in v2. An external health log exists from 2026-10-19 00:29:31 IST onward (`results/benchmark-v2/health_log.tsv`, written by `scripts/health_watch.py`, once a minute, read-only). Runs before that are not covered, including the P1 runs and the first ask-first fault runs. Triage checks each later run's time window against this log and marks any run during which a required container was unhealthy or restarted unexpectedly.**

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
