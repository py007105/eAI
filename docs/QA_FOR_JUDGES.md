# Questions we expect, with truthful answers

Numbers come from `docs/results/benchmark.md` (v1) only. Where the honest answer is "we did not test that", it says so.

> **Three findings first (benchmark v1, `docs/results/benchmark.md`; not buried, not softened):**
> 1. **The ask-first arm is invalid.** The benchmark harness handed the brain and the simulated operator the placeholder token `change-me` (an import of the config module loaded it from `.env`), so the brain refused every approval (HTTP 503) and the operator ignored the refusal; the first proposal then sat unapproved and, because a pending approval never expires, blocked all later detection (42 of 45 runs). Its 0 of 30 recoveries say nothing about ask-first operation (`docs/postmortems/ask-first-arm-stuck-incident-v1.md`). Both faults are fixed on the v2 branch and evaluated on fresh seeds.
> 2. **False alarms on healthy runs.** The autopilot opened an incident in 8 of 10 healthy runs and recreated a container in 4 of 5 traffic surges (it called a surge a memory leak). threshold_restart had 5 of 10 false alerts and prototype_rules 8 of 10 (`docs/postmortems/autopilot-healthy-runs-v1.md`).
> 3. **Recovery is self-reported.** It comes from the system's own checkout; the independent measure is the load generator's failed-request %. No independent probe logs exist.
>
> Also true: the benchmark brains were configured without LLM keys (the report provider is not recorded per run), forecasting is implemented and unit-tested but its live lead time was not demonstrated (an attempted live check was stopped by low memory, and two smoke runs ended before the resource limit), and 27 of 30 autopilot runs reporting recovery is one application, five runs per cell, scripted faults. v2 is a proposal only (`docs/V2_PROPOSAL.md`).

| arm (v1) | self-reported recovery, 30 supported runs | failed-request % (mean) | seconds to self-reported recovery (mean) | healthy runs with a false alert (of 10) | harmful interventions on healthy runs |
|---|---|---|---|---|---|
| no_action | 0 | 32.17 | - | 0 | 0 |
| threshold_restart | 12 | 26.60 | 68.2 | 5 | 0 |
| prototype_rules | 9 | 26.29 | 69.4 | 8 | 0 |
| eternalai_ask_first (invalid, see finding 1) | 0 | 31.99 | - | 0 (detection blocked) | 0 |
| eternalai_autopilot | 27 | 18.39 | 50.0 | 8 | 4 |

Source: `docs/results/benchmark.md`, sections 1b and 4 (rendered from `results/benchmark-v1/benchmark_raw.jsonl`). Where the autopilot does **not** beat the baselines: threshold_restart recovered `crash` in 4 of 5 runs against the autopilot's 2 of 5 (both orders crashes abstained); on `latency` the autopilot's failed-request % (8.1) is higher than threshold_restart's (4.0), and on `memory_leak` it is higher than no_action's (11.2 against 0.4) because its own container recreation fails requests; its false-alert count on healthy runs is worse than threshold_restart's and equal to prototype_rules'; and the pooled failed-request % and detection-time differences against threshold_restart and prototype_rules have intervals that include zero, so they are not distinguishable at n = 5 per cell.


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
By design it abstains when a window is unlike anything it was trained on or its confidence is low (on the unseen fault cpu_burn the autopilot abstained correctly in 4 of 5 runs; it also abstained on both crashes of `orders`, a missed recovery on a supported fault; see `docs/postmortems/crash-orders-seed100-v1.md`). It also gives a short grace period after a release change, because a normal rolling release restarts the service for a few seconds; a bad release is still caught once errors persist. The cost of the grace is slower detection of bad deploys by up to that period.

**Is the dashboard real?**
It reads the live backend over REST and shows real incidents. The screenshots in `docs/screenshots/` use fixture data to show layout and are labelled that way.

**Is it safe to give it Docker access?**
The backend mounts the Docker socket, which is root-equivalent on the host. In this repository that is a demo configuration: the approve, reject and mode endpoints are refused until a real token is set, only four allow-listed runbooks exist, and nothing from the LLM or from a user string reaches a shell. It is not a hardened deployment.

**Did you copy code from other projects?**
No code. Patterns were taken from the projects listed in `docs/REFERENCES.md` (several have no licence, so ideas only); attributions are in `NOTICE`.

**What would you do next?**
Test on a second application; add an evaluator-side recovery probe with retained raw logs; store the abstention reason and confidence in every incident row; compare real LLM reports with template reports over many incidents; and run the shuffled-label control on the live data.
