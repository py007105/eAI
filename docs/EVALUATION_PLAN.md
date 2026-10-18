# Evaluation plan (pre-registered)

Written while the held-out benchmark is running and **before any benchmark result was read**. Its git commit time is the
evidence for that. Where this plan is silent, nothing may be decided after seeing results; where it is wrong, the correction is
written as a dated amendment at the bottom, never by editing the text above it.

## 0. What had been seen before this plan was committed (full disclosure)

- Smoke tests on seeds that are in neither the training range (1000-1707) nor the benchmark range (below 1000): about 25 runs
  across all arms. They were used to find and fix plumbing bugs (listed in `docs/DATA.md`). They are not reported as results.
- Benchmark completion counts only, plus **two rows** of the first arm (`eternalai_autopilot`) that were opened to check that rows are
  well-formed: `disk_fill` seed 104 (detected, recovered) and `crash` seed 100 on `orders` (detected, **not recovered**). The second one
  motivated the triage rules in section 9. No other benchmark row has been read.

## 1. System under test

- Models: frozen at git tag `models-v1` (data hash `de7253cb...`, see `docs/MODEL_CARD.md`). Never retrained during the benchmark.
- System code: git tag `benchmark-system-v1` (commit `245d3e7`). The images were built from that code (image creation time is after the
  last commit that touched `eternalai/`, `evaluator/`, `app/`, `models/` or `loadgen/`).
- The runner records `git rev-parse --short HEAD` of the working tree in every row. Arm 1 recorded `245d3e7`; arms started later record
  `3b29de5`, which differs from the tag **only** in `docs/DATA.md` (verified with `git diff --stat benchmark-system-v1 HEAD`).
- Live dependencies on the working tree while the benchmark runs: `docker-compose.yml` (re-read at the start of each arm),
  `telemetry/prometheus.yml` (bind mount) and `scripts/run_benchmark.py` with `models/collect_runs.py` and `eternalai/` (re-imported at
  the start of each arm). None of these may change until the run ends. All other work happens in a separate git worktree.
- No LLM key is given to the brain during the benchmark: every report is expected to be the deterministic template report (see Amendment 3: configured by construction, not recorded per row).

## 2. Design

- Arms (5): `no_action`, `threshold_restart`, `prototype_rules`, `eternalai_ask_first`, `eternalai_autopilot`.
- Scenarios (9): crash, latency, error_spike, memory_leak, disk_fill, bad_deploy (supported faults); cpu_burn (the unseen fault, no runbook
  and no label); traffic_surge and good_deploy (healthy negatives).
- Repetitions: 5 per scenario per arm, so 45 runs per arm and **225 runs in total**.
- **Seeds are shared across arms (paired design).** seed = 100 + 10 x repetition + index of the scenario in the list above (crash 0 ... good_deploy 8).
  The evaluator derives the target service and the fault parameters from the seed, so for a given seed every arm faces the same fault on
  the same service with the same parameters. Run order inside a repetition is shuffled with a fixed generator and is the same in every arm.
- Run timeouts: 90 s (120 s memory_leak, 100 s disk_fill); healthy scenarios are observed for 60 s. A run ends early when every incident
  opened since the injection is closed and 8 s have passed. After each run the evaluator waits for the brain to be idle, restores the
  stack, and waits 45 s (200 s after a release change) before the next injection.
- Baselines: `threshold_restart` and `prototype_rules` are engine variants (`eternalai/baselines.py`) sharing the executor, policy engine,
  verification and incident de-duplication with the real brain. `prototype_rules` is the earlier prototype's detector constants, root-cause rule
  and action map ported onto this stack's signals; it is **not** the prototype's code running unchanged, so its results are indicative.
  Release-grace logic exists only in the real brain.
- Fault delivery differs from the training data in one respect (leak and disk faults run inside the service process now; see `docs/DATA.md`).

## 3. Who approves in ask-first mode

`eternalai_ask_first` uses a **simulated operator**: a thread in `scripts/run_benchmark.py` that polls `/approvals` every 1 s and approves
any proposal once it has been pending for 5.0 s (so the effective delay is 5-6 s), using the approval token. It always approves and never
rejects, so there is no human judgement in it. Differences between ask-first and autopilot are therefore about 5-6 s of added delay per
action plus anything that changes while waiting; they say nothing about how well a person would approve.

## 4. Metric definitions (computed only by `scripts/render_results.py` from `docs/results/benchmark_raw.jsonl`)

Primary metrics, each reported per scenario and per arm:

1. **Verified-recovery rate**: runs of the six supported fault scenarios in which the brain's verification outcome was `recovered`, over the runs in that cell. For `cpu_burn` recovery is reported separately and is not expected from EternalAI by design.
2. **Time to verified recovery**: seconds from injection to the verification timestamp, over recovered runs only.
3. **Failed-request %**: failed over total requests of the load generator between injection and the end of the observation window, from Prometheus counters read by the evaluator. Independent of the brain.
4. **Detection time**: seconds from injection to the first incident opened at or after the injection, over detected runs.
5. **Root-cause top-1 and top-3**: the injected service is first / among the first three in the first incident's ranking, over the six supported fault scenarios (not defined for `no_action`).
6. **False alerts on healthy runs**: runs of `traffic_surge` and `good_deploy` in which at least one incident was opened.
7. **Harmful interventions**: executed actions on a service other than the injected target (all fault runs), plus every executed action in a healthy run.
8. **Abstention on the unseen fault**: on `cpu_burn`, the first incident has `abstained = true` (cause `insufficient_evidence`). A clean escalation with no action is the intended outcome there.

Secondary, reported but not used for conclusions: cause-label accuracy, incidents opened per run (duplicates), actions executed.

## 5. Who scores recovery (and the limit of that)

- **Recovery is self-reported by the system under test.** `recovered` comes from the incident's `verification.outcome`, produced by the brain's
  own synthetic-checkout probes (`eternalai/verify.py`, 20 s window, all probes must pass with latency within 1 s). Baseline arms use the same
  verification code. The evaluator does **not** run an independent checkout probe, and **no raw probe logs exist** (`verify_recovery` returns
  only aggregates). Prometheus keeps only 2 hours, so the load generator's time series for finished runs are gone.
- What is independent: the failed-request % (point 3), computed by the evaluator from the load generator, and the evaluator's own record of the
  injection. Consistency check, fixed now: for every seed, a run that claims `recovered` should show a failed-request % no higher than the
  `no_action` arm's value for the same seed (the paired baseline), except for runs whose fault is not service-affecting; claimed recoveries that
  violate this are listed individually in the results.
- This is a **design limitation** (class (c) in section 9). A v2 of the harness may add evaluator-side probing with retained raw logs; that would
  be reported next to, and never instead of, the v1 numbers.

## 6. Run integrity

- **No run may be dropped.** All rows in the raw file enter every table.
- A run is a **harness failure** only if one of these holds, each with log evidence: the evaluator process crashed or returned a failed state; the Docker
  daemon failed or a container could not be (re)created; the injection never started (the evaluator's truth file has no injection record).
  Evidence: the progress log (`runtime/benchmark_progress.log`, copied to `docs/results/` at the end), the evaluator's `/truth` volume (one file per attempt) and container logs.
- A harness-failure run is **re-run with the same seed** (re-invoking the arm skips finished rows and retries the missing seeds). The failed
  attempt is **kept** (its log line and truth file), and the table shows both attempts.
- The runner does not write failed attempts to the raw file (it prints them to the progress log). That is a known gap in v1; the progress log is the record.
- Any other non-recovery is a result, not a failure.
- If the benchmark process dies, it is resumed only if the code is still exactly tag `benchmark-system-v1` (apart from documentation); the interruption and the
  restart are logged with timestamps in `docs/results/benchmark_interruptions.md`. Otherwise the run is stopped and reported.

## 7. Statistics and reporting rules

- Every cell (arm x scenario) shows **all 5 raw values** and their mean and min-max. No standard-deviation-only summaries.
- Bootstrap 95% intervals are used **only for pooled metrics** (all supported-fault runs of an arm, or a pooled paired difference), resampled by run (paired by seed for differences).
- **No significance claims between arms from n = 5 per cell.** Pooled differences are described with their intervals and nothing stronger. Words like "better"
  appear only for a pooled interval that excludes zero, and then with the number of runs.
- Every table is rendered by `scripts/render_results.py` from the raw rows; no number is typed by hand. The script is tested only on labelled fixture data.
- Results are reported for v1 exactly as run, including every metric where EternalAI is not better than a baseline.

## 8. Expectations stated in advance (from design and smoke tests, not from benchmark rows)

- `threshold_restart` acts without waiting to diagnose, so it is expected to have lower failed-request % and shorter time to recovery than EternalAI on
  simple faults (error spike, crash), while having no diagnosis, no abstention and false alerts on `good_deploy`.
- `cpu_burn`: EternalAI should abstain and escalate without acting, so it should show lower recovery than baselines that restart; this is the intended trade-off.
- `traffic_surge` should produce no incident in the real brain.
- The ported prototype rules may mis-diagnose and act on the wrong service; its port is approximate.
- `no_action` recovers nothing; it bounds the failed-request % of each fault.

## 9. Failure triage rule

Every non-recovery (and every metric surprise) is assigned exactly one class, with evidence from the run's incident log, timeline and logs:

- **(a) harness artifact**: the injection, restore, timing or scoring misbehaved (for example the run ended while an action was still in flight, or the fault outlived the run window).
- **(b) system bug**: EternalAI did something its own design says it should not (wrong target, an action that was allowed but crashed, a stuck incident, a classification that contradicts clear evidence).
- **(c) design limitation**: the system behaved as designed and the design cannot cover the case (no runbook for the cause, self-reported verification, detection delay by design).

A fix for a class (b) item, or a harness change for class (a), produces **v2** (new git tag, models unchanged unless the models are the bug), run on **fresh seeds** (a new
`--seed0`, still below 1000 and disjoint from v1's). **v1 results are never removed or replaced**; the final report shows v1 and v2 side by side. Nothing is changed in the v1 tree while v1 runs.

## 10. Known limits that apply to every conclusion

72 training runs on one application; faults are scripted and controlled; one machine and one workload generator; RE1 is laboratory telemetry rather than production data; the
cross-validation scores were produced after four iterations on the same data and are optimistic; n = 5 per cell; the Gemini path was verified with a small number of real calls and Groq not at all; recovery is
self-reported (section 5).

## Amendments

### Amendment 1 (2026-10-18, written while the benchmark is running; still no benchmark result read beyond completion counts and the two rows disclosed in section 0)

These are procedures for after the benchmark and wording rules. They change no v1 code, data or analysis rule above.

**A. Export before any reset.** Before any reset procedure (including the scorecard reset in `docs/DEMO.md`) and before touching the evaluator's volume, the raw results and the evaluator's truth files are exported and checksummed:
`docs/results/benchmark_raw.jsonl` and the contents of the `eai_truth` volume (one JSON per attempt plus `results.jsonl`) are copied under `results/benchmark-v1/`, with SHA-256 checksums in `results/benchmark-v1/SHA256SUMS`, and committed (or committed as an archive plus checksums
if too large). Only then may a reset be run. A reset is never run first.

**B. Orders-crash post-mortem, exact steps.** (1) Read the preserved evidence file for incident `e5267f50` and record the classifier's top class and probability, the abstain threshold in force and the recorded reason. (2) Tabulate which (fault, target service) pairs occur
in the 72 training runs (from `data/runs/*.json`) and in the benchmark rows. If the benchmark crashed a target that was never crashed in training, classify it (c) design limitation (weak generalisation across targets); otherwise look for a bug (b) and show the evidence. (3) Across all
scenarios and arms, check whether abstentions on supported faults cluster by target service, and report the table whatever it shows.

**C. Recovery is self-reported; wording rules.** Recovery stays class (c): the system under test reports it. In every document and rendered table the load generator's failed-request % is presented **first** as the independent measure, the consistency check against the `no_action` arm is shown next to it, and
recovery is called "self-reported" wherever it appears. No document may describe recovery as independently verified. (The word "verified" in a metric name means the system's own checkout verification.) A **proposal for v2, not applied**: evaluator-side probe logging that stores the raw probe result
of every probe per run (timestamp, status, latency), so recovery can be computed independently of the system under test.

**D. LLM path.** The benchmark used template reports only, because the brain container's LLM keys were empty (checked on the running container, without printing values). Every rendered table and results document states this. After the benchmark, with keys passed through compose, a small separate live LLM
check is run on non-benchmark seeds (excluded from all benchmark tables), reporting the schema-validity rate and latency. Before any demo, confirm the key variable is present in the brain container (presence only, never the value).

**E. Merge order.** `docs-prep` is merged into `main` only after the benchmark completes. Then the exact differences between the benchmark tree and tag `benchmark-system-v1` are listed (expected: documentation only).

### Amendment 2 (2026-10-18, written while the benchmark is running; no benchmark result read beyond completion counts and the two rows disclosed in section 0)

Adds two secondary analyses. Neither changes a v1 code path, a v1 row or an analysis rule above.

**F. Forecast lead time and false warnings (secondary metric).** For `memory_leak` and `disk_fill` runs: the time between the first forecast warning and the resource limit or the failure; and the number of forecast warnings raised on non-gradual runs (every other scenario).
The v1 raw rows store, per incident, only `id, opened_t, closed_t, kind, status, likely_cause, abstained, ranking, actions, verification, timeline`; they do **not** store the forecast objects or the time of the first warning. This metric is therefore reported as
**"not measured in benchmark v1"**. It is not inferred from `kind` or `opened_t`. It is measured instead by a dedicated live check on non-benchmark seeds (`docs/FORECAST_CHECK.md`, success criteria fixed there before it is run), reported separately, never pooled into benchmark tables.

**G. Offline RCAEval/PyRCA-style diagnosis baseline.** An offline comparison on the 72 training runs (71 used), grouped by run, of a simple RCAEval/PyRCA-style root-cause ranker against EternalAI's ranker on the same runs. It is labelled **offline**, uses no live arm and no
benchmark row, and is kept in its own file (`docs/results/offline_rca_baseline.md`). Only RE1 is available locally (RE2/RE3 are not downloaded), so no claim is made about those datasets. It is run only after the benchmark finishes.

**H. Order of post-benchmark work, with the Docker permission rule.** Docker is touched only after `benchmark_status` shows 225/225, no benchmark process is running, and the export-and-checksum step (A) is done. Then, in order: forecast check, offline RCA baseline, live LLM check,
preflight and the demo launcher (three runs from a clean `docker compose up`). Each reports what happened, including failures. Groq stays labelled untested.

### Amendment 3 (2026-10-18, written while the benchmark is running; no benchmark result read beyond completion counts and the two rows disclosed in section 0)

Corrects the wording of Amendment 1 D and section 1 on the LLM path. No v1 code, data or analysis rule changes.

**I. What is known about the LLM path in the benchmark, and how.** (1) By construction: `scripts/run_benchmark.py::start_brain` recreates the brain container for every brain arm with `GEMINI_API_KEY=""` and `GROQ_API_KEY=""` set in the launching environment, which overrides `.env` in compose. The `no_action` arm has no brain. So the benchmark brains were **configured** without LLM keys.
(2) Amendment 1 D says this was "checked on the running container"; that check was made earlier, is not recorded in any file, and cannot be repeated now without Docker commands, so it is not cited as evidence. (3) **The result rows do not record which provider produced a report.** The row's `incidents` entries keep `id, opened_t, closed_t, kind, status, likely_cause, abstained, ranking, actions, verification, timeline` and `brain_status` keeps `brain, mode, model_meta, calibration, fallbacks_in_use`; neither holds the report provider.
(4) The engine writes a timeline line `report by <provider> (...s)` only when a non-template provider answered (`eternalai/engine.py`, the `provider != "template"` branch). After the run, the rows' timelines are searched for that line; zero hits is consistent with template-only reports but is **not a direct record**.

**Wording rule from now on.** Documents say: "the benchmark brains were configured without LLM keys (by construction); the per-run report provider is not recorded in the rows, which is a design limitation (class c); the absence of 'report by <provider>' lines in the recorded timelines is consistent with template-only reports." Nothing asserts "template only" as a verified fact. A v2 would store the report provider in each incident row (proposal only, not applied).

### Amendment 4 (2026-10-18, v2 pre-registration, REDUCED PLAN; committed before any v2 data collection or rerun)

Written after the v1 benchmark and its post-mortems. Nothing here changes how v1 was analysed. v1 results are never removed or replaced and are reported beside v2. Three facts found after v1 shape this plan and are stated first, because they limit what v1 can be used for: (1) the harness gave the brain and the simulated operator the token `change-me`, so ask-first v1 measured nothing (`docs/postmortems/ask-first-arm-stuck-incident-v1.md`); (2) the trace collector (Jaeger) was OOM-killed before the first v1 benchmark run, so every v1 benchmark run had its apps exporting traces to a dead collector, a condition the training runs may not have shared (`docs/postmortems/surge-false-alarm-diagnosis.md`, addendum 2); (3) the detector's absolute memory limits are a few MB wide and the live stack's healthy memory differs from training by a few MB.

**J. The exact v2 changes** (branch `v2-dev`; tagged `benchmark-system-v2` before the evaluation; no change after the tag):

- **A.** A pending approval expires after `APPROVAL_TTL_S` = 120 s (escalated, evidence preserved); a pending approval does not block detection elsewhere; services (and their callers) covered by a pending incident open no duplicate; a watch-only observation closes after the same time.
- **B.** Incidents record `diagnosis` (top class and probability, answered label, abstention reason, novelty and its threshold, learned limits exceeded); benchmark rows keep `diagnosis`, `report_meta`, `forecasts`, `confidence`, `services`, the approver counters and the reset result.
- **C.** The benchmark token no longer comes from `ETERNALAI_APPROVAL_TOKEN` (an import loads `.env` into it); after an ask-first brain starts, the harness probes the approval API and aborts unless it answers 409; the operator logs every approve call.
- **D.** The harness resets the brain's per-run state through `POST /admin/reset` before each run.
- **E1. Telemetry condition**, chosen by the Stage 0 rule below, then identical for training data, evaluation and the paired baselines. The compose file now makes `OTEL_SDK_DISABLED` an environment switch (default unchanged) and caps Jaeger's store with `MEMORY_MAX_TRACES`.
- **E2. Memory features that tolerate baseline drift.** A new feature `mem_rel_growth` = (memory now, mean of the feature window, minus the median memory over the 150 s history from 150 s to 60 s ago) divided by the memory limit. The absolute-level memory inputs `mem_ratio`, `mem_z` and `mem_share` (and their `_obs` flags) leave the classifier's inputs, and `mem_share` leaves the detector's features and learned limits; `mem_slope_share_per_min` stays. Absolute memory stays available to the forecaster and to the evidence text. No scenario name, surge flag or injection parameter is an input.
- **E3. Retraining**, same code and nested-CV procedure as v1, on the original 72 training runs plus the fresh runs below, all grouped by run; thresholds chosen on training data only; frozen as `models-v2` with data hashes. The v1 benchmark runs and the surge-capture runs are seen data and are NOT used to train, select a threshold or tune.
- **E4. Fresh training data** (34 runs, seeds 1800-1842 from the unused training block, `docs/v2_seed_plan.json`): 12 `traffic_surge` (6 at intensity 25 and 6 at 40), 6 `good_deploy` on varied targets, 3 `crash` on `orders` and 3 on `payments`, and one or two each of `bad_deploy`, `latency`, `error_spike`, `memory_leak`, `disk_fill` aimed at the (fault, target) pairs v1 training lacked. No `cpu_burn` (the unseen fault). Collection conditions: the stack runs under the chosen telemetry condition; at least 45 minutes of continuous load generator traffic before the first run; two batches at least 60 minutes apart with the stack left running; the age of every container at the start of each run is recorded by `scripts/safe_collect.py` (`stack_ages` in each truth file). Collection uses the retry-safe collector with the memory guard.

**K. Stage 0 (telemetry condition; diagnostic, non-benchmark seeds, decided by a rule fixed here).** Six `traffic_surge` runs at intensity 40 on the remaining capture seeds 3604, 3608, 3614, 3620, 3621, 3624, two per condition, with the v2 brain in watch-only mode: T1 = Jaeger running with the capped store; T2 = Jaeger stopped and the exporter on (the condition of the v1 benchmark and of the first six captures); T3 = `OTEL_SDK_DISABLED=true` and Jaeger stopped. A condition **qualifies** when, in both its runs, (i) the peak `web` memory during the surge minus the median `web` memory before it is at most 3 MB and the same holds for `inventory`, and (ii) the pre-surge median of `web` and of `inventory` lies within 3 MB of the training median (web 66.8 MB, inventory 65.3 MB); `orders` and `payments` are reported but not used (their data volumes confound them). The first qualifying condition in the order T3, T1, T2 is used for everything that follows. If none qualifies, T3 is used and the finding "the exporter does not explain the surge growth" is recorded; the plan then continues unchanged. Jaeger is never needed by the brain (no code reads it), and the dashboard is not started for any v2 run; both are declared here and are off for every arm, the training collection and the baselines alike (except Jaeger under T1).

**L. Seeds** (`docs/v2_seed_plan.json`, checked by `scripts/check_seed_ranges.py`, `docs/results/seed_check_v2.md`; disjoint from v1 100-148, v1 training 1000-1707, smoke 2000-2999, forecast and LLM checks, capture 3600-3624): evaluation seeds 200-318 built as seed0 (200) + 10 x repetition + scenario index; fresh training seeds 1800-1842.

**M. The reduced evaluation: 95 runs.** In priority order:

| priority | arm | runs | what |
|---|---|---|---|
| P1 | `eternalai_autopilot` | 24 | 12 `traffic_surge` (both intensities as drawn from the seeds: 4 at 25, 8 at 40) and 12 `good_deploy` |
| P1 | `threshold_restart` | 24 | the same 24 seeds (paired) |
| P1/P2 | `eternalai_ask_first` | 8 | 4 `traffic_surge` and 4 `good_deploy` (the first four repetitions: enough to show it no longer blocks) |
| P2 | `eternalai_ask_first` | 18 | the 6 supported faults x 3 repetitions |
| P3 | `eternalai_autopilot` | 21 | the 6 supported faults and the unseen `cpu_burn`, x 3 repetitions: all six, because E2 and E3 change the detector and classifier for every fault |
| P4 | `no_action`, `threshold_restart` and `prototype_rules` on faults | 0 | **not run.** No v2 claim about the baselines on faults is made. Where v1 baselines are cited they are labelled v1, other seeds, and made with the dead trace collector. |

**N. Pass criteria (fixed now).** v1 reference values (autopilot, 30 supported runs): 30/30 detected, mean detection 12.1 s, self-reported recovery 27/30 (90%), failed-request % 18.39, healthy runs with a false alert 8/10, 4 container recreations in 5 surges. v2 against v1 is unpaired (different seeds) and said so. For the autopilot unless noted:

1. **No run blocked by a pending approval (ask-first, 26 runs).** In every ask-first row `approver.approve_failures == 0` and `approver.thread_errors == 0`; the preflight probe passed; none of the 18 supported-fault runs is `undetected`; and at least 15 of those 18 report recovery.
2. **Incidents on healthy runs:** at most 2 of the 24 autopilot healthy runs open an incident, and no more than `threshold_restart` opens on the same 24 seeds.
3. **Actions on healthy runs:** 0 executed actions in the 24 autopilot healthy runs (so 0 container recreations in the 12 surges) and 0 in the 8 ask-first healthy runs.
4. **Detection on supported faults not materially worse than v1:** all 18 supported runs detected and mean detection time at most 15.1 s (v1 12.1 s plus 25%).
5. **Recovery not materially worse than v1:** at least 15 of the 18 supported runs report recovery (v1 90% minus 10 percentage points, rounded up), and no scenario cell below 2 of 3 (1 of 3 for `crash`, where v1 managed 2 of 5).
6. **Failed-request %:** the pooled mean over the 18 supported runs is at most 23.4% (v1 18.39 plus 5 points). Reported unpaired against v1; no claim against `no_action` is made for v2.
7. **Unseen fault:** abstains correctly in at least 2 of the 3 `cpu_burn` runs.

"Materially worse" means exactly criteria 4 to 6 and nothing else. A failed criterion is reported as failed. Nothing is retuned after seeing v2 results; any further change is v3.

**O. What the smaller sample can and cannot show.** It can show that the specific failures of v1 are gone or not: a blocked ask-first run, an incident or action on a healthy run, a recreation during a surge. With 24 healthy runs, zero false alarms bounds the false-alarm rate only to roughly 12% or less (95%, rule of three) and 2 of 24 is compatible with a true rate up to about 27%; it cannot establish a rate near zero. With 18 supported runs and 3 per scenario, it cannot show per-scenario differences, small changes in recovery or detection time, or any comparison with the baselines on faults, and the recovery rate is uncertain by tens of percentage points. v2-versus-v1 is unpaired and across different conditions (v1 had the dead collector), so differences are indications, not measured effects. Recovery is still self-reported.

**P. Demo rule.** v2 is shown in the demo only if every criterion 1 to 7 passes for the autopilot arm and criterion 1 passes for the ask-first arm on the fresh seeds. Otherwise the demo uses v1 with its issues stated plainly.

**Q. Rules for retraining and thresholds (G3b).** Fit only on the original 72 training runs and fresh runs from unused training-block seeds. v1 benchmark runs and the surge captures are seen data: not used to train, to select thresholds or to tune. No surge flag, scenario name or injection parameter reaches a model at inference. Surge handling comes from traffic-normalised and drift-tolerant features and healthy-surge training data, not from "ignore surges" rules. No limit is tuned on benchmark seeds.

**R. Run discipline.** Every v2 runner is resumable and writes each run atomically; before each run it waits (logging) while free RAM is under 1.0 GB (`scripts/memguard.py`, `--min-free-gb`). The same telemetry condition applies to every arm. The integrity, triage and statistics rules of sections 6, 7 and 9 apply unchanged, with the triage classes (a) harness artifact, (b) system bug, (c) design limitation. Sections 1-10 of this plan are otherwise unchanged.

## Amendment 5 (2026-10-18, recorded before any v2 evaluation run): Stage 1 execution record and the longer gap

Facts (log: `results/stage1/stage1_events.log`; times IST):
- Warm-up started 15:29. Batch 1 (17 runs) finished 17:04:12. The collector process was killed by the host's low-memory reaper at about 17:29, idle inside the gap, no run in flight, no result file affected (free RAM then 2.6 GB). The stack was not touched; all seven containers kept running with 0 restarts.
- Restart at 19:08 on the user's explicit order. The first launch failed at import (wrong Python, no run started). The second launch re-ran the batch-1 loop, skipped all 17 saved runs and overwrote `batch1_done` (17:04 -> 19:08); this was caught at once (19:10), the collector stopped, the script fixed (a batch's completion time is written once) and the original `batch1_done` restored. No run data was touched.
- Batch 2 started 19:10:28 and finished 20:04:52 (17 runs). **Actual gap between batches: 126 minutes (17:04 -> 19:10), against "at least 60 minutes" in E4.** The plan said *at least* 60, so the gap is within the pre-registered condition, but it is about twice the nominal value; the intent was not to shorten it and it was not shortened.
- Automatic resumes used: 0 of 3 (the one restart was a user order).

Effect on claims: batch 2 was collected on older containers than a 60-minute gap would have given (the apps' start times were 16:27 to 17:04 IST, so about 2 h 10 min to 2 h 40 min old at batch 2 start and about 3 h to 3 h 40 min at its end; exact per-run ages are in each run file). This goes further in the direction E4 wanted (realistic ages and prior load). It does not change any pass criterion or analysis rule. What we can say: training batches were collected under T3 with at least 45 min warm-up and 126 min between batches. What we cannot say: that the gap was exactly 60 min, or anything about which gap length is needed; container ages per run are in each run file. The evaluation stack is recreated by `scripts/v2_stack.ps1`, so evaluation ages are not tied to these.

## Amendment 6 (2026-10-18, before any v2 result is read): attribution and wording rule for every document

v2 differs from v1 in four things at once: the retrained models (72 original + 34 fresh runs), the memory features (relative growth instead of absolute levels), the approval-queue fix (TTL, non-blocking pending approvals, benchmark token) and the telemetry condition (T3: exporter off, no Jaeger). The evaluation cannot separate them, so **no improvement or change may be attributed to any single one of them** in the README, EVALUATION, DEMO, MODEL_CARD, QA_FOR_JUDGES or any slide. v2 is described only as "fixes for the failures v1 exposed, tested on fresh seeds", never as "the model is better". v1 and v2 are unpaired and use different seeds (v1 100-148, v2 200-318); v2 is a reduced plan with the sample sizes in section M. Any telemetry-related statement is labelled HYPOTHESIS unless a controlled test exists (see `docs/postmortems/telemetry-conditions-by-batch.md`).

## Amendment 7 (2026-10-19 00:29 IST, tooling only, during Stage 3): external health log

No per-run container-state record in v2. An external health log exists from 2026-10-19 00:29:31 IST onward (`results/benchmark-v2/health_log.tsv`, written by `scripts/health_watch.py`, once a minute, read-only). Runs before that are not covered, including the P1 runs and the first ask-first fault runs. Triage checks each later run's time window against this log and marks any run during which a required container was unhealthy or restarted unexpectedly. A required container down or repeatedly restarting outside a runbook action (not running in 3 consecutive samples, unhealthy in 3, or a RestartCount rise) is a stop trigger: the driver is left as it is and the user is alerted. No system code changed. Stage 3 also had one memory kill (see `results/benchmark-v2/stage3_events.log`) with an orphan evaluator run (`orphans.json`) excluded from all results.
