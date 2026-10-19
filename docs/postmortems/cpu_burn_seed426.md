# Post-mortem (read-only): cpu_burn seed 426, autopilot, run 4948fbf558

Status: read-only analysis of the exported v2 evidence. No model, threshold, policy or code was changed; the row stays in the evaluated set as recorded. Sources: `results/benchmark-v2/rerun/benchmark_v2_rerun_raw.jsonl` (row verbatim), `health_log_full.tsv`, `truth_and_evidence_after_rerun.zip` (evaluator truth), `stock_log.jsonl`.

## What happened (from the row)
- Injected: `cpu_burn`, 2 threads, target **orders**, t_inject 1792363588.66 (04:16:28 IST). Truth: `unseen_fault`, `supported: false`.
- Brain incident b26695a3 opened 7.4 s after injection ("anomaly confirmed on ['orders']"; services orders, web).
- Diagnosis (10 s later): class `latency_spike`, top probability 0.5835, **root cause ranked inventory 0.514, payments 0.353, orders 0.129, web 0.004** (the true target was third).
- Abstention gate: novelty **0.6093** against threshold **1.1166** (not novel); probability 0.5835 against `abstain_below` 0.4 (not low); only `lat_ratio` exceeded its limit. So the gate let the answer through (`abstained: false`).
- Policy: `restart_service` on **inventory**, verdict `execute`, reason "autopilot: low-risk runbook on allow-list", risk low. Executed at 1792363611.90 (5.6 s after the decision); result `ok: true, restarted: inventory`.
- Verification: 4 synthetic checkouts, 0 % success, last detail `ReadTimeout`, max probe latency 5.11 s; outcome `unresolved`, incident closed unresolved. Final status `unresolved`; recovered false.
- Measured impact: failed-request 27.71 % over a 58.8 s window.
- Report layer: provider `template` (no LLM call).

## Answers to the questions
1. **Action and target.** `restart_service` on the inventory container (`eai-inventory-1`). The injected fault was on orders. Health log: inventory StartedAt changed from 22:45:37Z (04:15:37 IST sample 04:16:08) to 22:46:51Z (sample 04:17:10); orders' StartedAt did not change (the fault is a process burn, not a container event). The restart touched a service that was not the injected target.
2. **Classification / confidence / novelty / threshold.** See above: latency_spike, 0.5835, 0.6093 vs 1.1166, abstain_below 0.4.
3. **Root-cause evidence and policy.** The ranker put inventory first at 0.514 with a flat spread (0.514 / 0.353); the true target was third. The policy then did what it is specified to do for a confident-enough, non-novel `latency_spike` on an allow-listed low-risk runbook. No policy rule was violated; the input to the policy was wrong.
4. **Impact.** Failed-request 27.71 % (window), synthetic checkouts 0/4 after the restart (ReadTimeout). Stock was not a factor (stock after run 95,230 minimum; no 409 probes).
5. **Evidence of harm.** The scorer's `harmful_interventions: 1` is only a definition (an executed action on a service that was not the injected target, `evaluator/scoring.py` line 44); it is not a measurement of damage. What the records show: the action took the (otherwise unaffected) inventory service through a container restart while the checkout path was already failing on orders. Whether that restart added failed requests cannot be separated from the orders burn: there is **no unrestarted control for this seed**, and Prometheus no longer holds samples for this window (its earliest retained sample is about 1792390032, after the run), so no per-second series exists. **This is not classified as harmless; it is "an unnecessary restart of a healthy service during an outage, with unquantified added impact".** The restart did not fix the fault (verification 0/4), so there was no benefit either.
6. **Defect, limitation or statistical miss.** Evidence supports: (a) **model / generalization limitation** on an unseen fault: both the novelty gate (0.61 < 1.12) and the ranker (orders third) failed on this window, while seeds 406 and 416 (same fault, same 2 threads) had novelty 4.76 and 4.33 and abstained. (b) Not shown to be an implementation defect: the code path behaved as specified for its inputs, and I did not find an inconsistency between the logged decision and the policy. I did not test the novelty feature computation further (that would be new analysis, and no tuning is allowed), so a defect in the feature path is **not ruled out**, only not evidenced. (c) It is not a simple "expected miss": the pre-registered criterion 7 passed at 2/3, but the miss is real behaviour.

## Context (small samples, not a rate)
- v2 autopilot cpu_burn: abstained 2/3 (406, 416 yes; 426 no).
- v1 autopilot cpu_burn: abstained 4/5 (seed 126, target web, executed one action; its novelty was not recorded in that export).
- Across both versions the unseen-fault abstention is 6/8 observed, with 2 of 8 acting on a healthy or wrong service. These two samples are not paired and not enough to estimate an abstention rate; the honest statement is that abstention on unseen faults is not reliable.

## Consequences for the documents
- Never claim reliable abstention on unseen faults. The demo cpu_burn trial can fail the same way; the rehearsal plan treats "autopilot acts on a wrong service" as a possible outcome and says what to do (approval mode shows the same wrong proposal, a human rejects it).
- Mitigation in the design is the ask-first mode and the allow-list/cooldown; none of these is claimed to prevent a wrong restart.
- A fix (for example a stricter novelty rule, or requiring the ranking margin) would be a model/policy change: **v3, fresh seeds, not applied**.
