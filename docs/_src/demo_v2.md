**Numbers to quote (v2, filled from `docs/results/benchmark_v2.md`; caveats in `docs/EVALUATION.md`, canonical section):**

| say | value | say alongside it |
|---|---|---|
| supported faults, autopilot: recovered by its own check | {{ap_rec_k}} | 18 runs, 3 per fault type: "no failure observed", not a rate |
| supported faults, ask-first: recovered | {{af_rec_k}} | same sample size |
| healthy runs, autopilot: incidents opened | {{ap_hinc_k}} | the threshold-restart script on the same seeds: {{thr_hinc_k}} |
| healthy runs, autopilot: actions executed | {{ap_hact_k}} | 24 runs cannot rule out a rate of several percent |
| mean detection time, autopilot | {{ap_detect_s}} s | v1 was {{v1_ap_detect_s}} s: a tie within noise |
| mean failed-request %, autopilot (independent measure) | {{ap_failed}}% | no same-seed no-action reference in v2; not comparable with v1 |
| unseen fault (cpu_burn), autopilot abstained | {{cpu_v2}} in v2, {{v1_cpu}} in v1 | different seeds, never pooled |

**The unseen-fault segment (labelled as such, ask-first mode):** `python scripts/demo_challenge.py start --unseen`. Say before it starts: "this is a fault type EternalAI was never trained on. In our tests it abstained in {{cpu_v2}} v2 runs and {{v1_cpu}} v1 runs, and in one v2 run (seed {{s426_seed}}) it chose the wrong service: it ranked the true target {{s426_rank_target}}rd, did not flag the window as novel, and restarted `{{s426_acted}}` while the fault was on `{{s426_target}}`; failed requests were {{s426_fail}}% and the checkout probes {{s426_probes}}. We do not claim it abstains on unseen faults. That is why this segment runs in ask-first mode: it proposes, a human decides."

**If a judge picks an unseen fault while the autopilot is on (honest answer):** "The autopilot may abstain, escalate and keep the evidence, which is what it did in {{cpu_v2}} of our v2 runs and {{v1_cpu}} of our v1 runs of one unseen fault type. It may also act on the wrong service, which it did once in v2 (seed {{s426_seed}}). We did not measure how often on other faults, and we do not claim it knows when to stop. For an unseen fault, switch to ask-first so a human sees the proposed service and runbook before anything runs. What you see on screen is the proposal and the ranked services; whether that is enough for a human to spot a wrong target is recorded in the rehearsal log (`docs/results/demo_rehearsals.md`)."
