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
- No LLM key is given to the brain during the benchmark: every report is the deterministic template report.

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
