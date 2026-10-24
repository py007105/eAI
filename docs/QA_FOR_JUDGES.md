# Questions we expect, with truthful answers

Numbers come from the generated result files (`docs/results/benchmark.md` for v1, `docs/results/benchmark_v2.md` for v2). Where the honest answer is "we did not test that", it says so.

> **Three findings first (benchmark v1, `docs/results/benchmark.md`; not buried, not softened):**
> 1. **The ask-first arm is invalid.** The benchmark harness handed the brain and the simulated operator the placeholder token `change-me` (an import of the config module loaded it from `.env`), so the brain refused every approval (HTTP 503) and the operator ignored the refusal; the first proposal then sat unapproved and, because a pending approval never expires, blocked all later detection (42 of 45 runs). Its 0 of 30 recoveries say nothing about ask-first operation (`docs/postmortems/ask-first-arm-stuck-incident-v1.md`). Both faults are fixed on the v2 branch and evaluated on fresh seeds.
> 2. **False alarms on healthy runs.** The autopilot opened an incident in 8 of 10 healthy runs and recreated a container in 4 of 5 traffic surges (it called a surge a memory leak). threshold_restart had 5 of 10 false alerts and prototype_rules 8 of 10 (`docs/postmortems/autopilot-healthy-runs-v1.md`).
> 3. **Recovery is self-reported.** It comes from the system's own checkout; the independent measure is the load generator's failed-request %. No independent probe logs exist.
>
> Also true: the benchmark brains were configured without LLM keys (the report provider is not recorded per run), the pre-registered 20-run live forecast check (v3, `docs/results/forecast_check.md`) FAILED its memory-lead criterion (median lead 18.3 s against the 30 s target, warned in 5 of 5 runs) and passed for a gradual disk fill (median lead 86.4 s, 5 of 5), with 0 warnings in 10 healthy runs; its stated time-to-limit window held the actual time in 0 of 10 runs, and 27 of 30 autopilot runs reporting recovery is one application, five runs per cell, scripted faults. This box describes benchmark v1, which is kept unchanged; the v2 evaluation that followed is described below and in the canonical section of `docs/EVALUATION.md`.

| arm (v1) | self-reported recovery, 30 supported runs | failed-request % (mean) | seconds to self-reported recovery (mean) | healthy runs with a false alert (of 10) | harmful interventions on healthy runs |
|---|---|---|---|---|---|
| no_action | 0 | 32.17 | - | 0 | 0 |
| threshold_restart | 12 | 26.60 | 68.2 | 5 | 0 |
| prototype_rules | 9 | 26.29 | 69.4 | 8 | 0 |
| eternalai_ask_first (invalid, see finding 1) | 0 | 31.99 | - | 0 (detection blocked) | 0 |
| eternalai_autopilot | 27 | 18.39 | 50.0 | 8 | 4 |

Source: `docs/results/benchmark.md`, sections 1b and 4 (rendered from `results/benchmark-v1/benchmark_raw.jsonl`). Where the autopilot does **not** beat the baselines: threshold_restart recovered `crash` in 4 of 5 runs against the autopilot's 2 of 5 (both orders crashes abstained); on `latency` the autopilot's failed-request % (8.1) is higher than threshold_restart's (4.0), and on `memory_leak` it is higher than no_action's (11.2 against 0.4) because its own container recreation fails requests; its false-alert count on healthy runs is worse than threshold_restart's and equal to prototype_rules'; and the pooled failed-request % and detection-time differences against threshold_restart and prototype_rules have intervals that include zero, so they are not distinguishable at n = 5 per cell.


<!-- gen:qa_v2 -->
## Benchmark v2 (final): numbers and answers

Numbers in this block come from `docs/results/benchmark_v2.md` and `docs/results/benchmark_v1_v2.md`, filled in by `scripts/build_docs.py`. The caveats are in `docs/EVALUATION.md`, section "Canonical methodology, results and limitations: benchmark v2"; read it before quoting any figure. v2 is "fixes for the failures v1 exposed, tested on fresh seeds", not "the model is better"; v1 and v2 are unpaired.

| v2 figure | value |
|---|---|
| evaluated rows (valid original + replacement) | 95 (58 + 37) |
| autopilot, supported faults: detected / recovered by its own check | 18/18 [82%, 100%] / 18/18 [82%, 100%] |
| ask-first, supported faults: detected / recovered | 18/18 [82%, 100%] / 18/18 [82%, 100%] |
| autopilot, healthy runs: incidents / executed actions | 1/24 / 0/24 |
| threshold_restart, same healthy seeds: incidents | 6/24 |
| cpu_burn (unseen), autopilot abstained | 2/3 in v2; 4/5 in v1 (different seeds, not pooled) |
| mean detection time / mean failed-request % (autopilot, 18 supported runs) | 11.78 s / 11.15% |

**Why not simply restart on a threshold?**
On healthy runs the same-seed threshold_restart baseline opened an incident in 6/24 runs against 1/24 for the autopilot (v2 healthy seeds; the one autopilot incident was in a traffic surge). That is the only same-seed v2 baseline comparison. For supported faults v2 ran no baseline, so we do **not** claim the autopilot recovers better than a restart script. In v1 (different seeds, older system) threshold_restart recovered more `crash` runs than the autopilot (4 of 5 against 2 of 5) and was ahead on some other metrics (see the v1 results above). What a bare restart cannot do is choose between restart, rollback and cleanup, rank which service is the root cause, or explain itself, and it restarts on a healthy release change. Whether that is worth the extra complexity beyond this one application is not shown.

**Where is genuine ML used?**
Four learned components, all trained on this application's own runs (105 runs used, two telemetry conditions): per-service anomaly limits plus an IsolationForest (the forest adds nothing measurable over the learned limits, `docs/results/detector_margin.md`), a calibrated gradient-boosting fault classifier with a nearest-neighbour novelty gate, a gradient-boosting root-cause ranker, and a Theil-Sen trend forecaster (live check: memory lead FAILED, median 18.3 s vs 30 s; gradual disk fill PASSED, median 86.4 s). The policy, the runbooks and the verification are deterministic code; the LLM only writes the report and cannot act.

**Is this overfitted to one application?**
It is specific to one application, and we say so. Cross-validation scores are optimistic (same fault injector, four iterations), and the benchmark seeds use the same injector. The v2 counts (18/18 [82%, 100%] recovered, 1/24 healthy incidents) come from 3 runs per fault type and carry wide intervals (an 18-of-18 result is consistent with a true rate near 82%). On public cross-system data fault classification transfers weakly (leave-one-system-out macro-F1 about 0.62, `docs/results/transfer_re1.md`). We have not shown that the models work on any other system.

**How would it work with other applications?**
The architecture is portable (metrics, container state, topology, allow-listed runbooks, a verification probe), but the **trained models are not**: they would need new training runs on the new application with a fault injector, and the runbooks and topology would have to be defined for it. Nothing here was tested on a second application.

**Can it accidentally harm healthy services?**
It can, and it did. In v1 the autopilot recreated a container in 4 of 5 traffic surges. In v2 seed 426 (an unseen fault on `orders`) the autopilot restarted `inventory`, a service that was not the target; failed requests were 27.71% and the checkout probes 0/4. Whether the restart added damage is unknown. The scorer calls such an action "harmful" only by definition (an executed action on a service other than the injected target), which is not a measurement of damage. In the 24 healthy v2 autopilot runs no action was executed (0/24), but 24 runs cannot rule out a rate of several percent. Mitigations are the allow-list, cooldowns, a circuit breaker and the ask-first mode, where a human approves; none is claimed to prevent a wrong restart.

**What happens when it encounters an unknown failure?**
It is designed to abstain (insufficient evidence, no action, evidence kept, escalate), and it did so in 2/3 v2 runs and 4/5 v1 runs of the one unseen fault we tried, on different seeds. That is not a reliable property: in seed 426 the novelty gate did not fire (novelty 0.61 against a threshold of 1.12) and the autopilot acted on the wrong service. We tried one unseen fault type only. For an unseen fault, ask-first mode shows the proposal to a human before anything runs; in autopilot mode the honest answer is "it may abstain and it may also act wrongly; we measured both".

**How is recovery verified?**
By the system itself: a synthetic checkout through all four services, held over a window; only a full pass counts as "recovered". That is an **internal** verification. The independent measure is the load generator's failed-request %, which the evaluator reads; it measures user impact, not proof of recovery, and v2 has no same-seed no-action arm to compare it with. No independent probe logs exist.

**What evidence supports generalization?**
Little, and limited: the models were scored on seeds they never saw (v1 100-148, v2 200-318 and 400-429), including one fault type held out of training (cpu_burn: abstained in 2/3 v2 and 4/5 v1 runs, with one wrong-service restart in v2), and the failure modes v1 exposed (blocked ask-first, healthy-run incidents) recurred much less in v2 on different seeds (ask-first never blocked; 1/24 autopilot healthy runs opened an incident), at small sample sizes. Against that: one application, one fault injector, one machine, n = 3 per fault type, unpaired v1/v2 comparisons, two telemetry conditions in training. We make no claim of generalization to other systems or of production readiness.
<!-- /gen:qa_v2 -->

**Isn't a cross-validation macro-F1 near 1.0 just overfitting?**
Not in the sense of leakage: every split is by whole run (never by random rows), calibration and thresholds are fitted inside training folds, and the data check found no label-bearing columns and no run-order effect. But it is optimistic for three honest reasons: the faults are strong and cleanly injected
by the same script that produced the training data; we iterated four times on the same cross-validation data (the first attempt scored 0.365, and every change is logged in `docs/DATA.md`), so there are forking paths; and there is a single application. The test that matters is the held-out benchmark on seeds the models never saw: autopilot root-cause top-1 30/30 and top-3 30/30 over the supported runs, failed requests 18.39% against 32.17% with no action, 27/30 self-reported recoveries (`docs/results/benchmark.md`); the same benchmark also shows the false-alarm and surge problems stated at the top of this file.
We did not run a shuffled-label control on the live data (we did on the public RE1 data, where it stayed at chance).

**Does it work on a different application?**
Not tested, and we do not claim it. The only cross-system evidence is on public RCAEval RE1 data, where fault classification across systems is weak (leave-one-system-out macro-F1 about 0.62 for the current model, 95% interval [0.586, 0.644], from `docs/results/transfer_re1.md`), and the same features let a model identify *which system* a row came from. Attempts to fix that (per-system normalisation, dropping identifying features) did not improve it with a confidence interval above zero.
The live models are specific to this application's signals.

**What happens when recovery fails?**
Verification runs a synthetic checkout through all four services for a window; only a full pass is "recovered", otherwise "partially recovered" or "unresolved". Failed or abstained cases are escalated with the evidence preserved; a cooldown and a circuit breaker (after two interventions on a service) stop repeated attempts; the same ongoing anomaly does not open a new incident every few seconds.
A real example from the benchmark, with what the log does and does not show, is in `docs/postmortems/`. Honest detail: a clean escalation is correct behaviour, but when a runbook existed for the cause it is also a missed recovery, and we say so.

**How do you know the LLM isn't making things up?**
It cannot act. Its output must validate against a strict schema, the evidence ids it cites must exist, the runbook it names must be one the deterministic table allows for the diagnosed cause, and the engine's own diagnosis stays authoritative when it disagrees. The first real Gemini call returned a correct diagnosis but invalid fields (free text where a list was required), and the validator rejected it; we then constrained the output with a response schema instead of loosening the validator.
What is **not** checked: the prose of the summary beyond those constraints. The model was tried on a handful of real calls (see the limitations in `docs/EVALUATION.md`), Groq was never tried, and the benchmark brains were configured without LLM keys, so the LLM is not expected to contribute to the benchmark numbers. The report provider is not recorded per run, so we cannot prove that from the rows; we only check that no recorded timeline contains a non-template `report by` line.

**Why not just restart a service when a threshold is crossed?**
That is a baseline in the benchmark (`threshold_restart`). On simple faults it acts immediately and is expected to be faster; in smoke tests it was. What it does not do: diagnose, choose between restart, rollback and cleanup, abstain on something unfamiliar, or avoid reacting to a healthy deployment (it raised an alert on a healthy release in smoke tests).
The measured comparison, including the metrics where EternalAI is not ahead: the table at the top of this file and sections 1b, 4 and 6 of `docs/results/benchmark.md`. In short: the autopilot recovered more runs (self-reported) and had lower failed-request % pooled, but it is not ahead of threshold_restart on `crash` (2/5 against 4/5), on healthy-run false alerts, or on the unseen fault, and several pooled differences against the baselines have intervals that include zero.

**Isn't the benchmark rigged, since you wrote the faults and the models?**
Partly, and we say so. The evaluator is independent code with a private truth volume, the models never see the fault name, and the benchmark uses unseen seeds and shares them across arms. But the same team wrote the fault injector that generated the training data, so the benchmark measures in-distribution performance on one application. It is not a test against faults we did not think of, other than the one deliberately unseen type.

**Who decides recovery?**
In v1 the system under test does (its own verification probe), so recovery is self-reported and never independently verified; we lead with the load generator's failed-request % for that reason. The evaluator contributes an independent failed-request percentage from the load generator and a consistency check against the no-action arm for the same seed, but no independent probe logs exist. That is a stated limitation and a candidate change for a v2.

**Did you change anything after seeing results?**
The analysis plan was committed before any result was read (`docs/EVALUATION_PLAN.md`; its commit time is the evidence), and the v1 system is a git tag. Fixes found after seeing results become a v2 on fresh seeds, reported next to v1 and never replacing it. Before the benchmark we did fix many bugs found by smoke tests on seeds outside both the training and benchmark ranges; those are listed in `docs/DATA.md`.

**How many runs, how many repetitions?**
72 training runs (71 used). The benchmark has 225 runs: 5 arms x 9 scenarios x 5 repetitions. Five per cell is too few to compare arms cell by cell, so only pooled differences with bootstrap intervals are reported, and no significance is claimed from single cells.

**Why does it sometimes do nothing?**
By design it abstains when a window is unlike anything it was trained on or its confidence is low (v1 only here; on the unseen fault cpu_burn the v1 autopilot abstained correctly in 4 of 5 runs, and the v2 figures, including a wrong-service restart in seed 426, are in the v2 block above, not pooled with v1; it also abstained on both crashes of `orders`, a missed recovery on a supported fault; see `docs/postmortems/crash-orders-seed100-v1.md`). It also gives a short grace period after a release change, because a normal rolling release restarts the service for a few seconds; a bad release is still caught once errors persist. The cost of the grace is slower detection of bad deploys by up to that period.

**Is the dashboard real?**
It reads the live backend over REST and shows real incidents. The screenshots in `docs/screenshots/` use fixture data to show layout and are labelled that way.

**Is it safe to give it Docker access?**
The backend mounts the Docker socket, which is root-equivalent on the host. In this repository that is a demo configuration: the approve, reject and mode endpoints are refused until a real token is set, only four allow-listed runbooks exist, and nothing from the LLM or from a user string reaches a shell. It is not a hardened deployment.

**Did you copy code from other projects?**
No code. Patterns were taken from the projects listed in `docs/REFERENCES.md` (several have no licence, so ideas only); attributions are in `NOTICE`.

**What would you do next?**
Test on a second application; add an evaluator-side recovery probe with retained raw logs; store the abstention reason and confidence in every incident row; compare real LLM reports with template reports over many incidents; and run the shuffled-label control on the live data.

## Is v2 better than v1? Which change fixed what?
We cannot say, and we do not claim it. v2 changed four things at once: the retrained models, the memory features, the approval-queue fix and the telemetry condition (T3: trace exporter off, no collector). The evaluation cannot separate them, and v1 and v2 used different seeds with different sample sizes (v2 is a reduced plan), so the two tables are not paired. What v2 shows is whether the specific failures v1 exposed (blocked ask-first runs, incidents and actions on healthy runs, a container recreated during a surge) recur on fresh seeds, judged by criteria fixed before collection (Amendment 4). Whether the dead trace collector in the v1 benchmark caused its memory shift is a hypothesis supported by a small diagnostic, not a finding.

## What are the incidents the dashboard shows when no challenge is running?
Those are incidents EternalAI opened while no fault was injected: it flagged unusual metrics, abstained with "insufficient evidence", escalated, and took no action. We don't know their cause. No recovery actions ran; their operational impact wasn't evaluated. We list all seven seen up to the end of rehearsal R4 in `docs/results/demo_rehearsal_R4.md` rather than hide them. They are rehearsal observations, not part of the frozen v2 benchmark statistics.
