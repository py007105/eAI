# Questions we expect, with truthful answers

Numbers are `[[placeholders]]` until `docs/results/benchmark.md` exists; they are filled from that file only. Where the honest answer is "we did not test that", it says so.

**Isn't a cross-validation macro-F1 near 1.0 just overfitting?**
Not in the sense of leakage: every split is by whole run (never by random rows), calibration and thresholds are fitted inside training folds, and the data check found no label-bearing columns and no run-order effect. But it is optimistic for three honest reasons: the faults are strong and cleanly injected
by the same script that produced the training data; we iterated four times on the same cross-validation data (the first attempt scored 0.365, and every change is logged in `docs/DATA.md`), so there are forking paths; and there is a single application. The test that matters is the held-out benchmark on seeds the models never saw: `[[held-out cause-label accuracy, failed-request % and self-reported recovery rates]]`.
We did not run a shuffled-label control on the live data (we did on the public RE1 data, where it stayed at chance).

**Does it work on a different application?**
Not tested, and we do not claim it. The only cross-system evidence is on public RCAEval RE1 data, where fault classification across systems is weak (`[[leave-one-system-out macro-F1 from transfer_re1.md]]`), and the same features let a model identify *which system* a row came from. Attempts to fix that (per-system normalisation, dropping identifying features) did not improve it with a confidence interval above zero.
The live models are specific to this application's signals.

**What happens when recovery fails?**
Verification runs a synthetic checkout through all four services for a window; only a full pass is "recovered", otherwise "partially recovered" or "unresolved". Failed or abstained cases are escalated with the evidence preserved; a cooldown and a circuit breaker (after two interventions on a service) stop repeated attempts; the same ongoing anomaly does not open a new incident every few seconds.
A real example from the benchmark, with what the log does and does not show, is in `docs/postmortems/`. Honest detail: a clean escalation is correct behaviour, but when a runbook existed for the cause it is also a missed recovery, and we say so.

**How do you know the LLM isn't making things up?**
It cannot act. Its output must validate against a strict schema, the evidence ids it cites must exist, the runbook it names must be one the deterministic table allows for the diagnosed cause, and the engine's own diagnosis stays authoritative when it disagrees. The first real Gemini call returned a correct diagnosis but invalid fields (free text where a list was required), and the validator rejected it; we then constrained the output with a response schema instead of loosening the validator.
What is **not** checked: the prose of the summary beyond those constraints. The model was tried on a handful of real calls (see the limitations in `docs/EVALUATION.md`), Groq was never tried, and the benchmark itself used only the template report, so the LLM contributes nothing to the benchmark numbers.

**Why not just restart a service when a threshold is crossed?**
That is a baseline in the benchmark (`threshold_restart`). On simple faults it acts immediately and is expected to be faster; in smoke tests it was. What it does not do: diagnose, choose between restart, rollback and cleanup, abstain on something unfamiliar, or avoid reacting to a healthy deployment (it raised an alert on a healthy release in smoke tests).
The measured comparison, including the metrics where EternalAI is not ahead: `[[pooled comparison and "not ahead" list from benchmark.md]]`.

**Isn't the benchmark rigged, since you wrote the faults and the models?**
Partly, and we say so. The evaluator is independent code with a private truth volume, the models never see the fault name, and the benchmark uses unseen seeds and shares them across arms. But the same team wrote the fault injector that generated the training data, so the benchmark measures in-distribution performance on one application. It is not a test against faults we did not think of, other than the one deliberately unseen type.

**Who decides recovery?**
In v1 the system under test does (its own verification probe), so recovery is self-reported and never independently verified; we lead with the load generator's failed-request % for that reason. The evaluator contributes an independent failed-request percentage from the load generator and a consistency check against the no-action arm for the same seed, but no independent probe logs exist. That is a stated limitation and a candidate change for a v2.

**Did you change anything after seeing results?**
The analysis plan was committed before any result was read (`docs/EVALUATION_PLAN.md`; its commit time is the evidence), and the v1 system is a git tag. Fixes found after seeing results become a v2 on fresh seeds, reported next to v1 and never replacing it. Before the benchmark we did fix many bugs found by smoke tests on seeds outside both the training and benchmark ranges; those are listed in `docs/DATA.md`.

**How many runs, how many repetitions?**
72 training runs (71 used). The benchmark has 225 runs: 5 arms x 9 scenarios x 5 repetitions. Five per cell is too few to compare arms cell by cell, so only pooled differences with bootstrap intervals are reported, and no significance is claimed from single cells.

**Why does it sometimes do nothing?**
By design it abstains when a window is unlike anything it was trained on or its confidence is low (`[[abstention on the unseen fault, and false-abstention rate]]`). It also gives a short grace period after a release change, because a normal rolling release restarts the service for a few seconds; a bad release is still caught once errors persist. The cost of the grace is slower detection of bad deploys by up to that period.

**Is the dashboard real?**
It reads the live backend over REST and shows real incidents. The screenshots in `docs/screenshots/` use fixture data to show layout and are labelled that way.

**Is it safe to give it Docker access?**
The backend mounts the Docker socket, which is root-equivalent on the host. In this repository that is a demo configuration: the approve, reject and mode endpoints are refused until a real token is set, only four allow-listed runbooks exist, and nothing from the LLM or from a user string reaches a shell. It is not a hardened deployment.

**Did you copy code from other projects?**
No code. Patterns were taken from the projects listed in `docs/REFERENCES.md` (several have no licence, so ideas only); attributions are in `NOTICE`.

**What would you do next?**
Test on a second application; add an evaluator-side recovery probe with retained raw logs; store the abstention reason and confidence in every incident row; compare real LLM reports with template reports over many incidents; and run the shuffled-label control on the live data.
