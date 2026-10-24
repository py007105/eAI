## Benchmark v2 (final): numbers and answers

Numbers in this block come from `docs/results/benchmark_v2.md` and `docs/results/benchmark_v1_v2.md`, filled in by `scripts/build_docs.py`. The caveats are in `docs/EVALUATION.md`, section "Canonical methodology, results and limitations: benchmark v2"; read it before quoting any figure. v2 is "fixes for the failures v1 exposed, tested on fresh seeds", not "the model is better"; v1 and v2 are unpaired.

| v2 figure | value |
|---|---|
| evaluated rows (valid original + replacement) | {{n_eval}} ({{n_valid}} + {{n_rerun}}) |
| autopilot, supported faults: detected / recovered by its own check (v2 benchmark, old policy; current unattended v3: 10/30 recovered alone) | {{ap_det}} / {{ap_rec}} |
| ask-first, supported faults: detected / recovered (approvals by a simulated operator after 5 s (no person reviewed); v2 benchmark, old policy) | {{af_det}} / {{af_rec}} |
| autopilot, healthy runs: incidents / executed actions | {{ap_hinc_k}} / {{ap_hact_k}} |
| threshold_restart, same healthy seeds: incidents | {{thr_hinc_k}} |
| cpu_burn (unseen), autopilot abstained | {{cpu_v2}} in v2; {{v1_cpu}} in v1 (different seeds, not pooled) |
| mean detection time / mean failed-request % (autopilot, 18 supported runs) | {{ap_detect_s}} s / {{ap_failed}}% |

**Why not simply restart on a threshold?**
On healthy runs the same-seed threshold_restart baseline opened an incident in {{thr_hinc_k}} runs against {{ap_hinc_k}} for the autopilot (v2 healthy seeds; the one autopilot incident was in a traffic surge). That is the only same-seed v2 baseline comparison. For supported faults v2 ran no baseline, so we do **not** claim the autopilot recovers better than a restart script. In v1 (different seeds, older system) threshold_restart recovered more `crash` runs than the autopilot (4 of 5 against 2 of 5) and was ahead on some other metrics (see the v1 results above). What a bare restart cannot do is choose between restart, rollback and cleanup, rank which service is the root cause, or explain itself, and it restarts on a healthy release change. Whether that is worth the extra complexity beyond this one application is not shown.

**Where is genuine ML used?**
Four learned components, all trained on this application's own runs (105 runs used, two telemetry conditions): per-service anomaly limits plus an IsolationForest (the forest adds nothing measurable over the learned limits, `docs/results/detector_margin.md`), a calibrated gradient-boosting fault classifier with a nearest-neighbour novelty gate, a gradient-boosting root-cause ranker, and a Theil-Sen trend forecaster (live check: memory lead FAILED, median 18.3 s vs 30 s; gradual disk fill PASSED, median 86.4 s). The policy, the runbooks and the verification are deterministic code; the LLM only writes the report and cannot act.

**Is this overfitted to one application?**
It is specific to one application, and we say so. Cross-validation scores are optimistic (same fault injector, four iterations), and the benchmark seeds use the same injector. The v2 counts (v2 benchmark, old policy, autopilot arm without approvals; current unattended v3: 10/30 recovered alone) ({{ap_rec}} recovered, {{ap_hinc_k}} healthy incidents) come from 3 runs per fault type and carry wide intervals (an 18-of-18 result is consistent with a true rate near {{wilson_lo_18}}%). On public cross-system data fault classification transfers weakly (leave-one-system-out macro-F1 about 0.62, `docs/results/transfer_re1.md`). We have not shown that the models work on any other system.

**How would it work with other applications?**
The architecture is portable (metrics, container state, topology, allow-listed runbooks, a verification probe), but the **trained models are not**: they would need new training runs on the new application with a fault injector, and the runbooks and topology would have to be defined for it. Nothing here was tested on a second application.

**Can it accidentally harm healthy services?**
It can, and it did. In v1 the autopilot recreated a container in 4 of 5 traffic surges. In v2 seed 426 (an unseen fault on `orders`) the autopilot restarted `inventory`, a service that was not the target; failed requests were {{s426_fail}}% and the checkout probes {{s426_probes}}. Whether the restart added damage is unknown. The scorer calls such an action "harmful" only by definition (an executed action on a service other than the injected target), which is not a measurement of damage. In the 24 healthy v2 autopilot runs no action was executed ({{ap_hact_k}}), but 24 runs cannot rule out a rate of several percent. Mitigations are the allow-list, cooldowns, a circuit breaker and the ask-first mode, where a human approves; none is claimed to prevent a wrong restart.

**What happens when it encounters an unknown failure?**
It is designed to abstain (insufficient evidence, no action, evidence kept, escalate), and it did so in {{cpu_v2}} v2 runs and {{v1_cpu}} v1 runs of the one unseen fault we tried, on different seeds. That is not a reliable property: in seed 426 the novelty gate did not fire (novelty {{s426_novelty}} against a threshold of {{s426_thr}}) and the autopilot acted on the wrong service. We tried one unseen fault type only. For an unseen fault, ask-first mode shows the proposal to a human before anything runs; in autopilot mode the honest answer is "it may abstain and it may also act wrongly; we measured both".

**How is recovery verified?**
By the system itself: a synthetic checkout through all four services, held over a window; only a full pass counts as "recovered". That is an **internal** verification. The independent measure is the load generator's failed-request %, which the evaluator reads; it measures user impact, not proof of recovery, and v2 has no same-seed no-action arm to compare it with. No independent probe logs exist.

**What evidence supports generalization?**
Little, and limited: the models were scored on seeds they never saw (v1 100-148, v2 200-318 and 400-429), including one fault type held out of training (cpu_burn: abstained in {{cpu_v2}} v2 and {{v1_cpu}} v1 runs, with one wrong-service restart in v2), and the failure modes v1 exposed (blocked ask-first, healthy-run incidents) recurred much less in v2 on different seeds (ask-first never blocked; {{ap_hinc_k}} autopilot healthy runs opened an incident), at small sample sizes. Against that: one application, one fault injector, one machine, n = 3 per fault type, unpaired v1/v2 comparisons, two telemetry conditions in training. We make no claim of generalization to other systems or of production readiness.
